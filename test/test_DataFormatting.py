import unittest
import pandas as pd
import DataFormatting

class TestCases(unittest.TestCase):

    ### ====================================
    ### Tests for create_holding_dataframe()
    ### ====================================

    def utility_create_holding_dataframe(self, testNum, rootpath):        
        # Load the test data
        dfTransactions = pd.read_csv(f"{rootpath}transactions_{testNum}.csv")
        dfIncome = pd.read_csv(f"{rootpath}income_{testNum}.csv")
        dsDateSeries = pd.read_csv(f"{rootpath}date_series_{testNum}.csv")
        dfClosePrices = pd.read_csv(f"{rootpath}close_prices_{testNum}.csv")    

        # ensure the columns are in the correct format
        dfTransactions['Settle date'] = pd.to_datetime(dfTransactions['Settle date'])
        dfTransactions['Quantity'] = pd.to_numeric(dfTransactions['Quantity'], errors='coerce').astype('float')
        dfTransactions['Value (£)'] = pd.to_numeric(dfTransactions['Value (£)'], errors='coerce').astype('float')

        dfIncome['Settle date'] = pd.to_datetime(dfIncome['Settle date'])
        dfIncome['Quantity'] = pd.to_numeric(dfIncome['Quantity'], errors='coerce').astype('float')
        dfIncome['Value (£)'] = pd.to_numeric(dfIncome['Value (£)'], errors='coerce').astype('float')       

        dsDateSeries['Settle date'] = pd.to_datetime(dsDateSeries['Settle date'])
        
        dfClosePrices['Settle date'] = pd.to_datetime(dfClosePrices['Settle date'])
        dfClosePrices['Close'] = pd.to_numeric(dfClosePrices['Close'], errors='coerce').astype('float')

        # load the expected results
        expected_df = pd.read_csv(f"{rootpath}expected_{testNum}.csv")

        # Ensure the expected DataFrame is in the correct format
        expected_df['Settle date'] = pd.to_datetime(expected_df['Settle date'])
        expected_df['Position name'] = expected_df['Position name'].astype(str)
        expected_df['Quantity'] = pd.to_numeric(expected_df['Quantity'], errors='coerce').astype('float')
        expected_df['Book cost'] = pd.to_numeric(expected_df['Book cost'], errors='coerce').astype('float')
        expected_df['Income Qty'] = pd.to_numeric(expected_df['Income Qty'], errors='coerce').astype('float')
        expected_df['Income'] = pd.to_numeric(expected_df['Income'], errors='coerce').astype('float')
        expected_df['Close'] = pd.to_numeric(expected_df['Close'], errors='coerce').astype('float')
        expected_df['Market value'] = pd.to_numeric(expected_df['Market value'], errors='coerce').astype('float')
        expected_df['Day PnL'] = pd.to_numeric(expected_df['Day PnL'], errors='coerce').astype('float')
        expected_df['ITD PnL'] = pd.to_numeric(expected_df['ITD PnL'], errors='coerce').astype('float')

        # Call the function
        result_df = DataFormatting.create_holding_dataframe(dfTransactions, dfIncome, dsDateSeries, dfClosePrices, 'Test Holding ABC')

        # Check if the result matches the expected DataFrame
        pd.testing.assert_frame_equal(result_df, expected_df)

    def test_create_holding_dataframe_example_1_simple(self):
        # define the root path for test data
        rootpath = "./test_data/create_holding_dataframe/"

        # Call the utility function with test number 1
        self.utility_create_holding_dataframe(1, rootpath)

    def test_create_holding_dataframe_example_2_no_income(self):
        # define the root path for test data
        rootpath = "./test_data/create_holding_dataframe/"

        # Call the utility function with test number 2
        self.utility_create_holding_dataframe(2, rootpath)

    def test_create_holding_dataframe_example_3_close_px_gaps(self):
        # define the root path for test data
        rootpath = "./test_data/create_holding_dataframe/"

        # Call the utility function with test number 3
        self.utility_create_holding_dataframe(3, rootpath)
    
    def test_create_holding_dataframe_example_4_buy_and_sells(self):
        # define the root path for test data
        rootpath = "./test_data/create_holding_dataframe/"

        # Call the utility function with test number 4
        self.utility_create_holding_dataframe(4, rootpath)

    def test_create_holding_dataframe_example_5_income_into_pnl(self):
        # define the root path for test data
        rootpath = "./test_data/create_holding_dataframe/"

        # Call the utility function with test number 5
        self.utility_create_holding_dataframe(5, rootpath)

    ### ============================
    ### Tests for create_portfolio()
    ### ============================


    ### =================================
    ### Tests for drop_unwanted_columns()
    ### =================================

    def test_drop_unwanted_columns_simple(self):
        # Sample DataFrame
        df = pd.DataFrame({
            'Settle date': ['2023-01-01', '2023-01-02'],
            'Position Name': ['A', 'B'],
            'Adj Qty': [10, 20],
            'Value (£)': [100, 200],
            'Unwanted Column': [1, 2]
        })

        columns_to_keep = ['Settle date', 'Position Name', 'Adj Qty']

        # Call the function
        result_df = DataFormatting.drop_unwanted_columns(df, columns_to_keep)

        # Expected DataFrame
        expected_data = {
            'Settle date': ['2023-01-01', '2023-01-02'],
            'Position Name': ['A', 'B'],
            'Adj Qty': [10, 20]
        }
        expected_df = pd.DataFrame(expected_data)

        # Check if the result matches the expected DataFrame
        pd.testing.assert_frame_equal(result_df, expected_df)

    def test_drop_unwanted_columns_no_cols_specified(self):
         # Sample DataFrame
        df = pd.DataFrame({
            'Settle date': ['2023-01-01', '2023-01-02'],
            'Position Name': ['A', 'B'],
            'Adj Qty': [10, 20],
            'Value (£)': [100, 200]
        })

        columns_to_keep = []

        # Call the function
        result_df = DataFormatting.drop_unwanted_columns(df, columns_to_keep)

        # Expected DataFrame
        expected_data = { }
        expected_df = pd.DataFrame(expected_data)

        # Check if the result matches the expected DataFrame
        pd.testing.assert_frame_equal(result_df, expected_df)

    def test_drop_unwanted_columns_no_cols_match(self):
         # Sample DataFrame
        df = pd.DataFrame({
            'Settle date': ['2023-01-01', '2023-01-02', '2023-01-03'],
            'Position Name': ['A', 'B', 'C'],
            'Adj Qty': [10, 20, 30],
            'Value (£)': [100, 200, 300]
        })

        columns_to_keep = ['A', 'B', 'C']

        # Call the function
        result_df = DataFormatting.drop_unwanted_columns(df, columns_to_keep)

        # Expected DataFrame
        expected_data = { }
        expected_df = pd.DataFrame(expected_data)

        print(result_df)

        # Check if the result matches the expected DataFrame
        pd.testing.assert_frame_equal(result_df, expected_df)