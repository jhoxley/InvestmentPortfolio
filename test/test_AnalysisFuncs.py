import unittest
import pandas as pd
import AnalysisFuncs as af

class TestCases(unittest.TestCase):
    
    ### ================================
    ### Tests for create_daily_summary()
    ### ================================
    def utility_create_daily_summary(self, testNum, rootpath):
        # Load the test data
        df = pd.read_csv(f"{rootpath}portfolio_{testNum}.csv")

        # Ensure the columns are in the correct format
        df['Settle date'] = pd.to_datetime(df['Settle date'])
        df['Position name'] = df['Position name'].astype('str')
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').astype('float')
        df['Book cost'] = pd.to_numeric(df['Book cost'], errors='coerce').astype('float')
        df['Income Qty'] = pd.to_numeric(df['Income Qty'], errors='coerce').astype('float')
        df['Income'] = pd.to_numeric(df['Income'], errors='coerce').astype('float')
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce').astype('float')
        df['Market value'] = pd.to_numeric(df['Market value'], errors='coerce').astype('float')
        df['Day PnL'] = pd.to_numeric(df['Day PnL'], errors='coerce').astype('float')
        df['ITD PnL'] = pd.to_numeric(df['ITD PnL'], errors='coerce').astype('float')

        # load the expected results
        expected_df = pd.read_csv(f"{rootpath}expected_summary_{testNum}.csv")

        # Ensure the expected DataFrame is in the correct format
        expected_df['Settle date'] = pd.to_datetime(expected_df['Settle date'])
        expected_df['Book cost'] = pd.to_numeric(expected_df['Book cost'], errors='coerce').astype('float')
        expected_df['Market value'] = pd.to_numeric(expected_df['Market value'], errors='coerce').astype('float')
        expected_df['ITD PnL'] = pd.to_numeric(expected_df['ITD PnL'], errors='coerce').astype('float')

        # Call the function
        result_df = af.create_daily_summary(df)

        # Check if the result matches the expected DataFrame
        pd.testing.assert_frame_equal(result_df, expected_df)

    # Test 1: trivial
    # Test 2: multiple positions, exist for all dates
    # Test 3: multiple positions, buys and sells mid-period
    # Test 4: multiple positions, matching sells closes position and re-opened later
    def test_create_daily_summary_1_single_pos(self):
        # define the root path for test data
        rootpath = "./test_data/create_daily_summary/"

        # Call the utility function with test number 1
        self.utility_create_daily_summary(1, rootpath)

    def test_create_daily_summary_2_multiple_pos(self):
        # define the root path for test data
        rootpath = "./test_data/create_daily_summary/"

        # Call the utility function with test number 2
        self.utility_create_daily_summary(2, rootpath)

    def test_create_daily_summary_3_buys_and_sells(self):
        # define the root path for test data
        rootpath = "./test_data/create_daily_summary/"

        # Call the utility function with test number 3
        self.utility_create_daily_summary(3, rootpath)

    def test_create_daily_summary_4_gap_reopen_pos(self):
        # define the root path for test data
        rootpath = "./test_data/create_daily_summary/"

        # Call the utility function with test number 4
        self.utility_create_daily_summary(4, rootpath)

    def test_create_daily_summary_5_income_into_pnl(self):
        # define the root path for test data
        rootpath = "./test_data/create_daily_summary/"

        # Call the utility function with test number 5
        self.utility_create_daily_summary(5, rootpath)

    ### =============================
    ### Tests for calculate_weights()
    ### =============================

    ### =============================
    ### Tests for calculate_returns()
    ### =============================

        