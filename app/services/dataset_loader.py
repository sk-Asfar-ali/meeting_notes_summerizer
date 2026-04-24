import pandas as pd
import os
import logging
import random

logger = logging.getLogger(__name__)

class DatasetLoader:
    def __init__(self, dataset_dir: str = "data/dataset"):
        self.dataset_dir = dataset_dir

    def get_available_files(self) -> list[str]:
        """Lists CSV or Parquet files in the dataset directory."""
        if not os.path.exists(self.dataset_dir):
            return []
        
        return [f for f in os.listdir(self.dataset_dir) if f.endswith('.csv') or f.endswith('.parquet')]

    def load_dataset(self, filename: str) -> pd.DataFrame:
        """Loads a dataset file."""
        file_path = os.path.join(self.dataset_dir, filename)
        try:
            if filename.endswith('.csv'):
                return pd.read_csv(file_path)
            elif filename.endswith('.parquet'):
                return pd.read_parquet(file_path)
        except Exception as e:
            logger.error(f"Error loading dataset {filename}: {e}")
        return pd.DataFrame()

    def get_random_sample(self, df: pd.DataFrame) -> dict:
        """Gets a random meeting transcript from the dataframe."""
        if df.empty:
            return None
            
        # Try to guess the transcript column
        transcript_cols = [col for col in df.columns if 'transcript' in col.lower() or 'text' in col.lower() or 'dialogue' in col.lower()]
        
        if not transcript_cols:
            logger.error("Could not find a transcript column in the dataset.")
            return None
            
        col_name = transcript_cols[0]
        idx = random.randint(0, len(df) - 1)
        row = df.iloc[idx]
        
        return {
            "title": f"Sample from {col_name} (Row {idx})",
            "transcript": str(row[col_name])
        }
