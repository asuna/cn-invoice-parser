import pdfplumber
import re
import os
import shutil
import argparse
from pathlib import Path

def extract_invoice_data(file_path):
    """
    Extracts Date, Seller Name, and Total Amount from a PDF invoice.
    """
    try:
        with pdfplumber.open(file_path) as pdf:
            # Standard invoices usually have Date and Seller on the first page
            first_page = pdf.pages[0]
            first_page_text = first_page.extract_text()
            
            if not first_page_text:
                return None, None, None

            # 1. Extract Date (from first page)
            # Pattern: matches "开票日期" with potential duplicates/spaces
            date_match = re.search(r'[开\s]+[票\s]+[日\s]+[期\s]+[:：]*\s*(\d{4}年\d{2}月\d{2}日)', first_page_text)
            invoice_date = date_match.group(1) if date_match else None

            # 2. Extract Amount
            # User requested "价税合计小写数值" (Total Price & Tax Lowercase Value)
            # In multi-page invoices, "价税合计" might be on the last page.
            # We iterate through all pages to find the Grand Total.
            
            amount = None
            
            # Priority 1: Look for "价税合计" followed by "小写" and the number across ALL pages
            for page in pdf.pages:
                page_text = page.extract_text()
                if not page_text:
                    continue
                    
                # Look for "价税合计" ... "小写" ... Number
                amount_match = re.search(r'[价\s]+[税\s]+[合\s]+[计\s]+.*?([小\s]+[写\s]+).*?[¥￥]?\s*([\d\.]+)', page_text, re.DOTALL)
                if amount_match:
                    amount = amount_match.group(amount_match.lastindex)
                    break # Found the grand total, stop searching
            
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
                clean_text = re.sub(r'\s+', '', text)
                # Look for 销售方...名称...
                # This is a bit risky if the text is jumbled, but worth a try as fallback
                if "销售方" in clean_text:
                    parts = clean_text.split("销售方")
                    if len(parts) > 1:
                        # Look for "名称" in the last part
                        name_match = re.search(r'名称[:：]?([\u4e00-\u9fa5]+)', parts[-1])
                        if name_match:
                            seller = name_match.group(1)

            return invoice_date, seller, amount

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None, None, None

def main():
    parser = argparse.ArgumentParser(description="Extract info from PDF invoices and rename them.")
    parser.add_argument('--input', default='invoices', help='Input directory containing PDF invoices')
    parser.add_argument('--output', default='output', help='Output directory for renamed files')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    
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
        date, seller, amount = extract_invoice_data(pdf_file)
        
        if date and seller and amount:
            # Format: Date-Seller-Amount.pdf
            # User requested "YYYY.MM.DD" format for date.
            # Original date format extracted is usually "YYYY年MM月DD日"
            formatted_date = date
            date_match = re.match(r'(\d{4})年(\d{2})月(\d{2})日', date)
            if date_match:
                formatted_date = f"{date_match.group(1)}.{date_match.group(2)}.{date_match.group(3)}"
            
            new_filename = f"{formatted_date}-{seller}-{amount}.pdf"
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
