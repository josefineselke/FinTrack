from abc import ABC, abstractmethod
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBox
from typing import List, Dict
import pandas as pd
import yaml
import re
import os

class AccountStatementParser(ABC):
    def __init__(self, filepath: str, categories: dict = None):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File {filepath} does not exist")
        self.filepath = filepath
        self.categories = categories or {}
        self.data = pd.DataFrame()

    @abstractmethod
    def extract_data(self) -> pd.DataFrame:
        # Extracts data from the file and returns it as DataFrame
        pass

class FileHandler():
    def __init__(self, filepaths: List[str] = None):
        # Initialize with empty list if no paths are provided 
        self.all_transactions = pd.DataFrame()
        self.filepaths = filepaths if filepaths else []
        self.output_paths = []

    def check_filepaths(self, paths: List[str]) -> List[str]:
        # Checks for new filepaths and adds them to the list
        self.output_paths = []  
        
        for filepath in paths:
            if filepath not in self.filepaths:
                self.output_paths.append(filepath)
                self.filepaths.append(filepath)
        
        return self.output_paths

    def get_all_filepaths(self) -> List[str]:
        # Returns all previously stored filepaths
        return self.filepaths
    
    def concatenate_transactions(self, new_transactions: pd.DataFrame):
        # Collects all transactions from all files
        if self.all_transactions.empty:
            self.all_transactions = new_transactions
        else:
            self.all_transactions = pd.concat([self.all_transactions, new_transactions], ignore_index=True)

    def save_transactions(self, filepath: str):
        # Saves all transactions to a csv file
        self.all_transactions.to_csv(filepath, sep=',', index=False, encoding='utf-8')

class NorisbankPDFParser(AccountStatementParser):
    """
    Parser for Norisbank PDF account statements.
    Extracts transactions, balances, and categorizes entries based on configured keywords.
    """
    
    # Pattern for date search
    DATE_PATTERN = r'\d{2}\.\d{2}\.\s*2024'
    
    # Pattern for amounts
    AMOUNT_PATTERN = r'\s*([+-])\s*((?:\d{1,3}\.)*\d{1,3},\d{2})'
    AMOUNT_PATTERN_CREDIT = r'\s*([+])\s*((?:\d{1,3}\.)*\d{1,3},\d{2})'
    AMOUNT_PATTERN_DEBIT = r'\s*([-])\s*((?:\d{1,3}\.)*\d{1,3},\d{2})'
    
    # Tolerance values
    BALANCE_TOLERANCE = 5.00  # For balance validation
    Y_COORDINATE_TOLERANCE = 20  # For text search in proximity
    X_COORDINATE_TOLERANCE = 10  # For amount search
    
    def __init__(self, filepath: str, categories: dict = None):
        """
        Initialize the Norisbank PDF parser.

        Args:
            filepath (str): Path to the PDF file
            categories (dict, optional): Dictionary containing category definitions and keywords
        """
        super().__init__(filepath, categories)

    def categorize_transaction(self, text: str) -> str:
        """
        Categorize a transaction based on its description using configured keywords.

        Args:
            text (str): Transaction description text

        Returns:
            str: Category name. Falls back to 'Personal' if no category matches
        """
        text_lower = text.lower()
        
        for category in self.categories.values():
            if any(keyword in text_lower for keyword in category['keywords']):
                return category['name']
        
        return 'Personal'

    def extract_balance(self, df: pd.DataFrame) -> tuple[float | None, float | None]:
        """
        Extract start and end balance from the account statement.

        Args:
            df (pd.DataFrame): DataFrame containing extracted text boxes from PDF

        Returns:
            tuple: (start_balance, end_balance), both can be None if not found
                  start_balance (float|None): Opening balance of the statement
                  end_balance (float|None): Closing balance of the statement
        """
        # Find rows with "EUR"
        eur_rows = df[df['text'].str.contains('^EUR$', regex=True, na=False)]
        start_balance = end_balance = None
        
        for _, eur_row in eur_rows.iterrows():
            # Search for "Old Balance" or "New Balance" nearby
            nearby_texts = df[
                (df['y0'] >= eur_row['y0'] - self.Y_COORDINATE_TOLERANCE) &
                (df['y0'] <= eur_row['y0'] + self.Y_COORDINATE_TOLERANCE)
            ]
            
            is_start = nearby_texts['text'].str.contains('Alter Saldo', case=False, na=False).any()
            is_end = nearby_texts['text'].str.contains('Neuer Saldo', case=False, na=False).any()
            
            # Search for corresponding amount
            potential_amounts = df[
                (df['y0'] == eur_row['y0']) &
                (df['y1'] == eur_row['y1']) &
                (df['text'].str.contains(self.AMOUNT_PATTERN, regex=True, na=False))
            ]
            
            if not potential_amounts.empty:
                amount_text = potential_amounts.iloc[0]['text']
                match = re.search(self.AMOUNT_PATTERN, amount_text)
                if match:
                    sign, amount = match.groups()
                    balance = float(amount.replace('.', '').replace(',', '.'))
                    if sign == '-':
                        balance = -balance
                        
                    if is_start:
                        start_balance = balance
                    elif is_end:
                        end_balance = balance
        
        return start_balance, end_balance

    def extract_data(self) -> pd.DataFrame:
        """
        Extract all transaction data from the PDF file.

        Processes the PDF file and extracts:
        - Transaction dates
        - Credit and debit amounts
        - Transaction purposes
        - Running balance
        - Categorizes transactions based on configured keywords

        Returns:
            pd.DataFrame: DataFrame containing all transactions with columns:
                - page: Page number in PDF
                - purpose: Categorized transaction purpose
                - debit: Debit amount (if applicable)
                - credit: Credit amount (if applicable)
                - currency: Transaction currency (EUR)
                - date: Transaction date
                - year: Transaction year
                - month: Transaction month
                - quarter: Transaction quarter
                - amount: Combined amount (positive for credit, negative for debit)
                - balance: Running account balance

        Raises:
            FileNotFoundError: If PDF file doesn't exist
            ValueError: If file is not a valid PDF
            Exception: For other processing errors
        """
        text_boxes = []
        current_page = 1
        
        # Extract Text Boxes from pdf
        for page in extract_pages(self.filepath):
            for element in page:
                if isinstance(element, LTTextBox):
                    text_boxes.append({
                        'page': current_page,
                        'x0': element.x0,
                        'y0': element.y0,
                        'x1': element.x1,
                        'y1': element.y1,
                        'text': element.get_text().strip()
                    })
            current_page += 1

        df = pd.DataFrame(text_boxes)
        
        # Extract start and end balance
        start_balance, end_balance = self.extract_balance(df)
        
        if start_balance is None:
            print("Warning: No start balance found!")
            start_balance = 0
        
        # Extract Date Entries  
        date_entries = df[df['text'].str.contains(self.DATE_PATTERN, regex=True, na=False)]

        # Extract Amount Entries for Credit and Debit
        amount_entries_credit = df[df['text'].str.contains(self.AMOUNT_PATTERN_CREDIT, regex=True, na=False)]
        amount_entries_debit = df[df['text'].str.contains(self.AMOUNT_PATTERN_DEBIT, regex=True, na=False)]
        amount_x1_credit = round(max(amount_entries_credit['x1'].value_counts().nlargest(2).index), 2)
        amount_x1_debit = round(max(amount_entries_debit['x1'].value_counts().nlargest(2).index), 2)

        # Find the smaller x0-coordinate for the booking date
        booking_x0 = min(date_entries['x0'].value_counts().nlargest(2).index)
        valuta_x0 = max(date_entries['x0'].value_counts().nlargest(2).index)
        
        # Extract Transactions
        transactions = []
        
        # Group by Page
        for page in df['page'].unique():
            page_df = df[df['page'] == page]
            
            # Extract all Booking Dates
            booking_dates = page_df[
                (page_df['x0'] == booking_x0) & 
                page_df['text'].str.contains(self.DATE_PATTERN, regex=True, na=False)
            ]
            for _, date_row in booking_dates.iterrows():
                # Extract all Entries with the same y1-coordinate; this marks one transaction
                same_y1_entries = page_df[page_df['y1'] == date_row['y1']]

                # Create new Transaction
                transaction = {
                    'booking_date': date_row['text'].replace('\n', '').strip(),
                    'purpose': None,
                    'debit': None,
                    'credit': None,
                    'currency': 'EUR'
                }

                # Extract information for the transaction
                for _, entry in same_y1_entries.iterrows():
                    amount_match = re.search(self.AMOUNT_PATTERN, entry['text'])
                    x_tolerance = 10

                    # Valuta can be skipped
                    if entry['x0'] == valuta_x0:
                        continue
                    elif amount_match and ( ((entry['x1'] - amount_x1_credit) < x_tolerance) or ((entry['x1'] - amount_x1_debit) < x_tolerance) ):
                        sign, amount = amount_match.groups()
                        if sign == '+':
                            transaction['credit'] = amount.replace('.', '').replace(',', '.')
                        elif sign == '-':
                            transaction['debit'] = sign + amount.replace('.', '').replace(',', '.')
                        continue
                    # All other entries are purpose
                    else:
                        transaction['purpose'] = self.categorize_transaction(entry['text'])
                
                transactions.append(transaction)

        # Create transactions dataframe
        df_transactions = pd.DataFrame(transactions)
        
        # Convert booking_date to datetime and create new date columns
        df_transactions['date'] = pd.to_datetime(df_transactions['booking_date'], format='%d.%m.%Y')
        df_transactions['year'] = df_transactions['date'].dt.year
        df_transactions['month'] = df_transactions['date'].dt.month
        df_transactions['quarter'] = df_transactions['date'].dt.quarter
        
        # Convert credit/debit to numeric values and calculate amount
        df_transactions['amount'] = round(pd.to_numeric(df_transactions['credit'].fillna('0')) + pd.to_numeric(df_transactions['debit'].fillna('0')), 2)
        
        # Sort by date
        df_transactions = df_transactions.sort_values('date')
        
        # Calculate running balance
        df_transactions['balance'] = round(start_balance + df_transactions['amount'].cumsum(), 2)
        
        # Validate end balance
        if end_balance is not None:
            calculated_end = df_transactions['balance'].iloc[-1]
            if abs(calculated_end - end_balance) > self.BALANCE_TOLERANCE:
                print(f"Warning: Calculated end balance ({calculated_end:.2f}) differs from actual end balance ({end_balance:.2f})!")
        
        # Drop original booking_date column
        df_transactions = df_transactions.drop('booking_date', axis=1)
        
        return df_transactions

class CSVParser(AccountStatementParser):
    def __init__(self, filepath: str, categories: dict = None):
        super().__init__(filepath, categories)

    def extract_data(self) -> pd.DataFrame:
        # Implementation for CSV files
        pass

