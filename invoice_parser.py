import pdfplumber
import re
import pdfplumber
import re
import os
import shutil
import argparse
from pathlib import Path
from openai import OpenAI

def get_invoice_summary(text, api_key, base_url, model, temperature):
    """
    Uses OpenAI API to summarize the invoice content into a short product description.
    """
    try:
        # Auto-append /v1 if missing and not already ending in a version number or 'v1'
        # This is a heuristic to help users who provide the root URL
        if base_url and not base_url.endswith('/v1') and not base_url.endswith('/v1/'):
             # Check if it looks like a root URL (no path)
             if base_url.count('/') <= 3: # https://example.com or https://example.com/
                 base_url = base_url.rstrip('/') + '/v1'
        
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        prompt = f"""
        Please analyze the following invoice text and extract a very short summary of the main goods or services purchased.
        
        Rules:
        1. Ignore tax categories enclosed in asterisks (e.g., ignore "*电线电缆*", "*餐饮服务*").
        2. Focus on the specific product name or common name (e.g., use "苹果转接头" instead of "电线电缆", use "笔记本电脑" instead of "电子设备").
        3. The summary must be concise, suitable for a filename (no special characters).
        4. Use Chinese if the invoice is Chinese.
        5. Max length: 15 characters.
        6. **RETURN ONLY THE SUMMARY TEXT. DO NOT INCLUDE "Output:" OR QUOTES.**
        
        Example: 
        Input: "*电线电缆*山泽Lightning转Type-C转接头..." -> "山泽转接头"
        Input: "*餐饮服务*客饭" -> "餐饮客饭"
        
        Invoice Text:
        {text[:2500]}
        """
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes invoices for file renaming. You return ONLY the summary text."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=30,
            temperature=temperature
        )
        
        if not hasattr(response, 'choices'):
             print(f"  -> AI Error: Unexpected response format. Response: {response}")
             return None

        summary = response.choices[0].message.content.strip()
        
        # Clean up common prefixes if the model ignores instructions
        summary = re.sub(r'^(Output|Summary|Answer)[:：\s]*', '', summary, flags=re.IGNORECASE)
        # Remove quotes and extra whitespace
        summary = summary.strip('"\' ')
        
        # Sanitize summary
        summary = re.sub(r'[<>:"/\\|?*\n\r]', '', summary)
        return summary
    except Exception as e:
        print(f"  -> AI Summarization failed: {e}")
        if "object has no attribute 'choices'" in str(e):
             print("     Hint: Check your --base-url. It might need '/v1' at the end.")
        return None

def extract_invoice_data(file_path):
    """
    Extracts Date, Seller Name, and Total Amount from a PDF invoice.
    Returns: date, seller, amount, full_text
    """
    try:
        with pdfplumber.open(file_path) as pdf:
            # Standard invoices usually have Date and Seller on the first page
            first_page = pdf.pages[0]
            first_page_text = first_page.extract_text()
            
            # Get full text for AI summary
            full_text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"
            
            if not first_page_text:
                return None, None, None, None

            # 1. Extract Date (from first page)
            # Pattern: matches "开票日期" with potential duplicates/spaces
            date_match = re.search(r'[开\s]+[票\s]+[日\s]+[期\s]+[:：]*\s*(\d{4}年\d{2}月\d{2}日)', first_page_text)
            invoice_date = date_match.group(1) if date_match else None

            # 2. Extract Amount
            # User requested "价税合计小写数值" (Total Price & Tax Lowercase Value)
            # In multi-page invoices, "价税合计" might be on the last page.
            # We iterate through all pages to find the Grand Total.
            
            amount = None
            
            # Priority 1: Look for "价税合计" ... "小写" ... Number
            amount_match = re.search(r'[价\s]+[税\s]+[合\s]+[计\s]+.*?([小\s]+[写\s]+).*?[¥￥]?\s*([\d\.]+)', full_text, re.DOTALL)
            if amount_match:
                amount = amount_match.group(amount_match.lastindex)
            
            # Priority 2: If not found, look for "小写" followed by currency symbol on FIRST page (Legacy/Fallback)
            if not amount:
                amount_match = re.search(r'[小\s]+[写\s]+.*?[¥￥]\s*([\d\.]+)', first_page_text)
                if amount_match:
                    amount = amount_match.group(1)
            
            # Priority 3: Fallback looking for just the number after 小写 on FIRST page
            if not amount:
                 amount_match = re.search(r'[小\s]+[写\s]+.*?\s*([\d\.]+)', first_page_text)
                 if amount_match:
                    amount = amount_match.group(1)

            # 3. Extract Seller Name (from first page)
            # Strategy: Find all occurrences of "名称". The last one is usually the Seller.
            # We also handle potential spaces in "名 称" and duplicates "名名称称".
            
            seller = None
            
            # Pattern: matches "名称" with potential duplicates/spaces
            # Note: Use [:：]* to handle multiple colons (e.g. ：：：) which might otherwise cause
            # the greedy name matching to backtrack and capture part of the key.
            matches = re.findall(r'[名\s]+[称\s]+[:：]*\s*([\u4e00-\u9fa5A-Za-z0-9\(\)（）]+)', first_page_text)
            
            if matches:
                # Filter matches to find the most likely Seller Name
                # 1. It should ideally contain "公司", "店", "行", "厂"
                # 2. It should NOT be a table header like "规格型号", "项目", "货物", "服务", "单位", "数量"
                
                candidates = []
                ignored_keywords = ["规格", "型号", "项目", "货物", "劳务", "服务", "单位", "数量", "单价", "金额", "税率", "税额"]
                
                for m in matches:
                    if any(k in m for k in ignored_keywords):
                        continue
                    candidates.append(m)
                
                # If we have candidates, prioritize those with company suffixes
                company_candidates = [c for c in candidates if any(s in c for s in ["公司", "店", "行", "厂", "局", "部"])]
                
                if company_candidates:
                    # Usually the seller is the last one (bottom of invoice)
                    seller = company_candidates[-1]
                elif candidates:
                    # If no clear company suffix, take the last valid candidate
                    seller = candidates[-1]
            
            # If the above fails (e.g. no colon), try looking for the block explicitly in the cleaned text
            if not seller:
                clean_text = re.sub(r'\s+', '', first_page_text)
                # Look for 销售方...名称...
                # This is a bit risky if the text is jumbled, but worth a try as fallback
                if "销售方" in clean_text:
                    parts = clean_text.split("销售方")
                    if len(parts) > 1:
                        # Look for "名称" in the last part
                        name_match = re.search(r'名称[:：]?([\u4e00-\u9fa5]+)', parts[-1])
                        if name_match:
                            seller = name_match.group(1)

            return invoice_date, seller, amount, full_text

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None, None, None, None

def extract_items_section(text):
    """
    Extracts the section containing product items to save tokens.
    Strategy: Look for "名称" (Name) header and "合计" (Total) footer.
    """
    lines = text.split('\n')
    start_index = -1
    end_index = -1
    
    # 1. Find Header Line
    # Look for line containing "名称" AND ("金额" or "单价" or "数量")
    for i, line in enumerate(lines):
        if "名称" in line and ("金额" in line or "单价" in line or "数量" in line):
            start_index = i
            break
            
    if start_index == -1:
        # Fallback: look for "名称" that is likely a header (not buyer/seller)
        for i, line in enumerate(lines):
            if "名称" in line and "购买方" not in line and "销售方" not in line:
                start_index = i
                break

    # 2. Find Footer Line (after start)
    if start_index != -1:
        for i in range(start_index + 1, len(lines)):
            if "合计" in lines[i] or "价税合计" in lines[i]:
                end_index = i
                break
    
    if start_index != -1 and end_index != -1:
        # Return content between header and footer
        return "\n".join(lines[start_index+1:end_index])
    elif start_index != -1:
        # Return everything after header if no footer found
        return "\n".join(lines[start_index+1:])
    else:
        # Fallback: Return original text if structure not found
        return text

def main():
    parser = argparse.ArgumentParser(description="Extract info from PDF invoices and rename them.")
    parser.add_argument('--input', default='invoices', help='Input directory containing PDF invoices')
    parser.add_argument('--output', default='output', help='Output directory for renamed files')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    
    # AI Arguments
    parser.add_argument('--api-key', help='OpenAI API Key')
    parser.add_argument('--base-url', default='https://api.openai.com/v1', help='OpenAI Base URL')
    parser.add_argument('--model', default='gpt-3.5-turbo', help='OpenAI Model to use')
    parser.add_argument('--temperature', type=float, default=0.3, help='AI Temperature (0.0-1.0)')
    
    args = parser.parse_args()
    
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    
    if not input_dir.exists():
        print(f"Input directory '{input_dir}' does not exist.")
        return

    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    print(f"Processing invoices from '{input_dir}' to '{output_dir}'...")
    
    count = 0
    for pdf_file in input_dir.glob('*.pdf'):
        if args.verbose:
            print(f"Processing: {pdf_file.name}")
        date, seller, amount, full_text = extract_invoice_data(pdf_file)
        
        if date and amount:
            # Determine the middle part of the filename: Summary or Seller
            middle_part = seller
            
            if args.api_key and full_text:
                if args.verbose:
                    print(f"  -> Generating AI summary...")
                
                # Optimize: Extract only the items section
                items_text = extract_items_section(full_text)
                if args.verbose:
                    print(f"     (Sending {len(items_text)} chars to AI instead of {len(full_text)})")
                
                summary = get_invoice_summary(items_text, args.api_key, args.base_url, args.model, args.temperature)
                if summary:
                    middle_part = summary
                    if args.verbose:
                        print(f"  -> Summary: {summary}")
            
            if not middle_part:
                middle_part = "Unknown"

            # Format: Date-Summary-Amount.pdf
            # User requested "YYYY.MM.DD" format for date.
            # Original date format extracted is usually "YYYY年MM月DD日"
            formatted_date = date
            date_match = re.match(r'(\d{4})年(\d{2})月(\d{2})日', date)
            if date_match:
                formatted_date = f"{date_match.group(1)}.{date_match.group(2)}.{date_match.group(3)}"
            
            new_filename = f"{formatted_date}-{middle_part}-{amount}.pdf"
            # Sanitize filename just in case (remove illegal chars for windows)
            new_filename = re.sub(r'[<>:"/\\|?*]', '', new_filename)
            
            dest_path = output_dir / new_filename
            
            try:
                shutil.copy2(pdf_file, dest_path)
                if args.verbose:
                    print(f"  -> Created: {new_filename}")
                count += 1
            except Exception as e:
                print(f"  -> Failed to copy: {e}")
        else:
            print(f"  -> Failed to extract all info for {pdf_file.name}. Date: {date}, Seller: {seller}, Amount: {amount}")

    print(f"\nDone. Processed {count} files.")

if __name__ == "__main__":
    main()
