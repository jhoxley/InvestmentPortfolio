import unittest
import pandas as pd
import AnalysisFuncs as af

class TestCases(unittest.TestCase):
    
    def test_CalculateWeights_Simple(self):
        # Sample DataFrame
        summary_data = {
            'Settle Date' : ['2023-01-01', '2023-01-02', '2023-01-03'],
            'Total_Market_Value': [600, 610, 620]
        }
        summary_frame = pd.DataFrame(summary_data)

        position_date = {
            'Settle Date': ['2023-01-01', '2023-01-01', '2023-01-01',
                            '2023-01-02', '2023-01-02', '2023-01-02',
                            '2023-01-03', '2023-01-03', '2023-01-03'
                            ],
            'Position Name':[ 'A', 'B', 'C',
                              'A', 'B', 'C',
                               'A', 'B', 'C'
                             ],
            'Book Market Value': [100, 200, 300,
                                  105, 195, 310,
                                  110, 190, 320],
        }
        position_frame = pd.DataFrame(position_date)

        # Calculate weights
        result_df = af.calculate_weights(position_frame, summary_frame)

        # Expected result
        expected_data = {
            'Settle Date': ['2023-01-01', '2023-01-01', '2023-01-01',
                            '2023-01-02', '2023-01-02', '2023-01-02',
                            '2023-01-03', '2023-01-03', '2023-01-03'
                            ],
            'Position Name':[ 'A', 'B', 'C',
                              'A', 'B', 'C',
                               'A', 'B', 'C'
                             ],
            'Book Market Value': [100, 200, 300,
                                  105, 195, 310,
                                  110, 190, 320],
            'Portfolio Weight %' : [100.0 / 600.0, 200.0 / 600.0, 300.0 / 600.0,
                                    105.0 / 610.0, 195.0 / 610.0, 310.0 / 610.0,
                                    110.0 / 620.0, 190.0 / 620.0, 320.0 / 620.0]
        }
        expected_df = pd.DataFrame(expected_data)

        # Check if the result matches the expected DataFrame
        pd.testing.assert_frame_equal(result_df.round(4), expected_df.round(4))