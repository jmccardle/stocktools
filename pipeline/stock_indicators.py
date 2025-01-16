import os
import pandas as pd
import talib
import config  # Import only the config file, no other project modules


class StockIndicators:
    """
    A class to encapsulate technical indicator calculations using configurations.
    """

    @staticmethod
    def calculate_macd(data):
        """
        Calculate MACD and Signal Line from stock data, using MACD_CONFIG.

        Parameters:
            data (pd.DataFrame): DataFrame containing stock data with 'Close' column.

        Returns:
            pd.DataFrame: DataFrame with MACD, Signal Line, Histogram, and crossovers.
            pd.Timestamp: Last Long Position Date (MACD Cross Up).
        """
        if 'Close' not in data.columns:
            raise ValueError("The input data must contain a 'Close' column.")

        # Use MACD_CONFIG for parameter values
        fast_length = config.MACD_CONFIG['fast_length']
        slow_length = config.MACD_CONFIG['slow_length']
        signal_length = config.MACD_CONFIG['signal_length']

        # Calculate MACD and Signal Line
        macd, signal, hist = talib.MACD(
            data['Close'],
            fastperiod=fast_length,
            slowperiod=slow_length,
            signalperiod=signal_length
        )

        # Detect Crossovers (MACD crossing above Signal Line)
        cross_up = (macd.shift(1) <= signal.shift(1)) & (macd > signal)
        #cross_down = (macd.shift(1) >= signal.shift(1)) & (macd < signal)

        # Add calculated columns to the DataFrame
        data['MACD'] = macd
        data['Signal Line'] = signal
        data['Histogram'] = hist
        data['Buy Signal'] = cross_up  # Rename to match generic signal terminology

        # Find the last "cross-up" position
        last_cross_up = data.loc[data['Buy Signal'], 'Datetime'].max() if not data.loc[data['Buy Signal']].empty else None
        #last_cross_up = data.loc[data['Sell Signal'], 'Datetime'].max() if not data.loc[data['Sell Signal']].empty else None

        return data, last_cross_up #last_cross_down


    @staticmethod
    def calculate_rsi(data, res='1D'):
        """
        Calculate Multi-Timeframe RSI with optional upper and lower line signals using TA-Lib.

        Parameters:
            data (pd.DataFrame): DataFrame containing stock data with 'Close' column.
            res (str): Resolution for multi-timeframe analysis (e.g., '1D', '1H').

        Returns:
            pd.DataFrame: DataFrame with RSI values and buy/sell signals.
            pd.Timestamp: Last Buy Signal Date (RSI crossing below lower line).
        """
        if 'Close' not in data.columns:
            raise ValueError("The input data must contain a 'Close' column.")

        # Extract RSI configuration parameters
        period = config.RSI_CONFIG['period']
        up_line = config.RSI_CONFIG['up_line']
        low_line = config.RSI_CONFIG['low_line']

        # Calculate RSI using TA-Lib
        rsi = talib.RSI(data['Close'], timeperiod=period)

        # Add the RSI values to the DataFrame
        data[f'RSI_{res}'] = rsi

        # Add signals based on RSI crossing below the lower line (buy signal)
        data['Buy Signal'] = (rsi < low_line) & (rsi.shift(1) >= low_line)
        #data['Sell Signal'] = ((rsi.shift(1) <= up_line) & (rsi > up_line)).astype(int)

        # Find the last "Buy Signal" position
        last_buy_signal = data.loc[data['Buy Signal'], 'Datetime'].max() if not data.loc[data['Buy Signal']].empty else None
        #last_sell_signal = data.loc[data['Sell Signal'], 'Datetime'].max() if not data.loc[data['Sell Signal']].empty else None

        return data, last_buy_signal #last_sell_signal

class StockScreener:
    """
    A class to handle stock screening based on multiple technical indicators.
    """
    def __init__(self, stock_dir):
        if not os.path.exists(stock_dir):
            raise FileNotFoundError(f"The directory {stock_dir} does not exist.")
        self.stock_dir = stock_dir

    def screen_by_indicators(self, indicators, output_file):
        """
        Process all stock data and find signals based on the given indicator functions.

        Parameters:
            indicators (list): List of indicator functions to apply to the stock data.
            output_file (str): File path to save the signals.
        """
        all_signals = []

        for file_name in os.listdir(self.stock_dir):
            if file_name.endswith(".csv"):
                stock_symbol = os.path.splitext(file_name)[0]
                file_path = os.path.join(self.stock_dir, file_name)

                # Load stock data
                data = pd.read_csv(file_path)
                if 'Datetime' not in data.columns:
                    raise ValueError(f"The file {file_name} must contain a 'Datetime' column.")
                data['Datetime'] = pd.to_datetime(data['Datetime'])

                for indicator in indicators:
                    # Apply the indicator function
                    result = indicator(data)

                    # Handle the result as a tuple
                    if isinstance(result, tuple):
                        data = result[0]  # Extract the modified DataFrame
                    else:
                        data = result  # Use result directly if it's not a tuple

                    # Check for buy signals and add indicator name to signal type
                    for signal_col in [col for col in data.columns if col == 'Buy Signal']:
                        signals = data.loc[data[signal_col], ['Datetime']].copy()
                        signals['symbol'] = stock_symbol
                        signals['signal type'] = indicator.__name__.replace('calculate_', '').upper()
                        all_signals.append(signals)

        if all_signals:
            # Combine all signals into a single DataFrame
            combined_signals = pd.concat(all_signals, ignore_index=True)

            # Save to the output file, appending if it exists
            combined_signals.to_csv(
                output_file,
                mode='a',
                header=not os.path.exists(output_file),  # Write header only if the file doesn't exist
                index=False,
                columns=['Datetime', 'symbol', 'signal type']  # Ensure proper column order
            )
            print(f"Signals appended to {output_file}")
        else:
            print("No signals detected.")


# Main Execution
if __name__ == "__main__":
    try:
        screener = StockScreener(stock_dir=config.STOCK_POST_DIR)

        # Screen stocks using multiple indicators
        screener.screen_by_indicators(
            indicators=[StockIndicators.calculate_macd, StockIndicators.calculate_rsi],
            output_file=config.CONSOLIDATED_OUTPUT_FILE
        )

    except Exception as e:
        print(f"Error: {e}")
