from parser.file_handling import FileHandler, NorisbankPDFParser, CSVParser
import csv
import glob2 as glob
import pandas as pd
import yaml
import os

def load_config():
    with open('config/config.yaml', 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def main():
    try:
        # Load configuration
        config = load_config()
        
        # Create output directory if it doesn't exist
        os.makedirs(config['paths']['output_dir'], exist_ok=True)
        
        # Collect files based on filetype
        filetype = config['files']['filetype'].lower()
        input_pattern = f"*.{filetype}"
        file_pattern = os.path.join(config['paths']['input_dir'], input_pattern)
        input_files = glob.glob(file_pattern)
        file_handler = FileHandler()
        
        # Process each file based on filetype
        for file_path in input_files:
            try:
                # Select appropriate parser based on filetype
                if filetype == 'pdf':
                    parser = NorisbankPDFParser(file_path, config['categories'])
                elif filetype == 'csv':
                    parser = CSVParser(file_path, config['categories'])
                else:
                    print(f"Unsupported file type: {filetype}")
                    continue
                
                transactions = parser.extract_data()
                if not transactions.empty:
                    file_handler.concatenate_transactions(transactions)
            except FileNotFoundError:
                print(f"File not found, skipping: {file_path}")
                continue
            except ValueError:
                print(f"Invalid file, skipping: {file_path}")
                continue
            except Exception as e:
                print(f"Error processing file, skipping: {file_path}")
                print(f"Error details: {str(e)}")
                continue
        
        # Try to save collected transactions
        try:
            if file_handler.all_transactions.empty:
                print("No transactions found to save!")
                return
            
            output_path = os.path.join(
                config['paths']['output_dir'], 
                config['files']['output_file']
            )
            file_handler.save_transactions(output_path)
            print(f"All transactions successfully saved to {output_path}")
            
        except PermissionError:
            print("CRITICAL ERROR: No write permissions for output file!")
            raise
        except Exception as e:
            print(f"CRITICAL ERROR saving transactions: {str(e)}")
            raise
            
    except FileNotFoundError:
        print("CRITICAL ERROR: Config file not found!")
        raise
    except yaml.YAMLError as e:
        print(f"CRITICAL ERROR in config file: {str(e)}")
        raise
    except Exception as e:
        print(f"CRITICAL ERROR in main program: {str(e)}")
        raise

if __name__ == '__main__':
    main()
