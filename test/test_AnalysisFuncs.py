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
        df['Book cost'] = pd.to_numeric(df['Book cost'], errors='coerce').astype('float')
        df['Market value'] = pd.to_numeric(df['Market value'], errors='coerce').astype('float')
        df['ITD PnL'] = pd.to_numeric(df['ITD PnL'], errors='coerce').astype('float')

        # load the expected results
        expected_df = pd.read_csv(f"{rootpath}expected_summary_{testNum}.csv")

        # Ensure the expected DataFrame is in the correct format
        expected_df['Settle date'] = pd.to_datetime(expected_df['Settle date'])
        expected_df['Total Book Cost'] = pd.to_numeric(expected_df['Total Book Cost'], errors='coerce').astype('float')
        expected_df['Total Market Value'] = pd.to_numeric(expected_df['Total Market Value'], errors='coerce').astype('float')
        expected_df['Total PnL'] = pd.to_numeric(expected_df['Total PnL'], errors='coerce').astype('float')
        expected_df['Total Return %'] = pd.to_numeric(expected_df['Total Return %'], errors='coerce').astype('float')
        expected_df['Daily Return %'] = pd.to_numeric(expected_df['Daily Return %'], errors='coerce').astype('float')

        # Call the function
        result_df = af.create_daily_summary(df)

        # Check if the result matches the expected DataFrame
        pd.testing.assert_frame_equal(result_df, expected_df)

    # Test 1: trivial
    # Test 2: multiple positions, exist for all dates
    # Test 3: multiple positions, buys and sells mid-period
    # Test 4: multiple positions, matching sells closes position and re-opened later
    def test_create_daily_summary_1(self):
        # define the root path for test data
        rootpath = "./test_data/create_daily_summary/"

        # Call the utility function with test number 1
        self.utility_create_daily_summary(1, rootpath)

    ### =============================
    ### Tests for calculate_weights()
    ### =============================

    ### =============================
    ### Tests for calculate_returns()
    ### =============================

        