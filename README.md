# CN Invoice Parser / 中国电子发票解析器

[English](#english) | [中文](#中文)

---

<a name="中文"></a>
## 中文说明

这是一个用于批量解析中国电子发票（PDF格式）的Python工具。它可以自动提取发票中的关键信息（开票日期、销售方名称、价税合计），并按照指定格式重命名文件。

### 功能特点

- **自动提取**：支持提取开票日期、销售方名称（智能识别公司名）、价税合计（小写数值）。
- **智能重命名**：将PDF文件重命名为 `日期-销售方-金额.pdf` 格式。
- **批量处理**：支持指定输入和输出目录，批量处理所有PDF文件。
- **鲁棒性强**：针对部分PDF中存在的文字重叠、乱码（如“开开票票日期”）等问题进行了特殊优化。

### 安装依赖

需要安装 `pdfplumber` 库：

```bash
pip install pdfplumber
```

### 使用方法

#### 基本用法

默认读取 `invoices` 目录下的PDF文件，并将结果输出到 `output` 目录：

```bash
python invoice_parser.py
```

#### 高级用法

您可以指定输入目录、输出目录，并开启详细日志：

```bash
python invoice_parser.py --input <输入目录> --output <输出目录> --verbose
```

**参数说明：**
- `--input`: 输入目录路径 (默认: `invoices`)
- `--output`: 输出目录路径 (默认: `output`)
- `--verbose`: 显示详细的处理日志

### 许可证

本项目采用 [MIT License](LICENSE) 许可证。允许免费用于商业用途，但需保留版权声明。

---

<a name="english"></a>
## English Description

This is a Python tool for batch parsing Chinese electronic invoices (PDF format). It automatically extracts key information (Invoice Date, Seller Name, Total Amount) and renames the files accordingly.

### Features

- **Automatic Extraction**: Extracts Invoice Date, Seller Name (smart company name recognition), and Total Amount (Tax Inclusive).
- **Smart Renaming**: Renames PDF files to `Date-Seller-Amount.pdf` format.
- **Batch Processing**: Supports specifying input and output directories to process all PDF files in bulk.
- **Robustness**: Optimized for common PDF issues like text overlapping or duplicated characters (e.g., garbled text layers).

### Installation

Requires `pdfplumber`:

```bash
pip install pdfplumber
```

### Usage

#### Basic Usage

By default, it reads PDF files from the `invoices` directory and outputs to the `output` directory:

```bash
python invoice_parser.py
```

#### Advanced Usage

You can specify input/output directories and enable verbose logging:

```bash
python invoice_parser.py --input <input_dir> --output <output_dir> --verbose
```

**Arguments:**
- `--input`: Path to input directory (default: `invoices`)
- `--output`: Path to output directory (default: `output`)
- `--verbose`: Enable verbose logging

### License

This project is licensed under the [MIT License](LICENSE). Commercial use is allowed, provided that copyright notice is retained.
