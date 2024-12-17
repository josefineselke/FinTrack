# FinTrack - Financial Transaction Processor

## Overview
FinTrack is a Python-based tool designed to process and categorize financial transactions from various input formats. It currently supports PDF bank statements from Norisbank and CSV files, converting them into a standardized format for further analysis.

## Features
- Supports multiple input file formats (PDF, CSV)
- Automatic transaction categorization based on configurable rules
- Consolidated output in CSV format
- Configurable via YAML configuration file
- Error handling and logging for robust processing

## Requirements
- Python 3.x
- Required packages:
  - pandas
  - pdfplumber (for PDF processing)
  - yaml
  - glob2
  - csv

## Setup
1. Clone the repository
2. Install required dependencies: `pip install -r requirements.txt`
3. Configure the `config/config.yaml` file with your settings

## Configuration
The `config.yaml` file contains:
- Input/output directory paths with default values
- File type settings (currently only PDF is fully supported)
- Transaction categorization rules

## Usage
1. Place your financial documents in the configured input directory (default: `./account_statements/`)
2. Run the program: `python main.py`
3. Find processed transactions in the output directory (default: `./output/`)

## File Structure
- `config/config.yaml`: Configuration file
- `parser/`: Directory for parser classes
- `main.py`: Main execution file

