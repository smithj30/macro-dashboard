"""
File upload provider — wraps modules/data_ingestion/file_loader.py.
"""

from typing import Any, Dict, Optional

import pandas as pd

from providers.base_provider import BaseProvider
from modules.data_ingestion.file_loader import load_uploaded_file, load_csv_from_path


class FileProvider(BaseProvider):

    @property
    def name(self) -> str:
        return "File Upload"

    def fetch_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Load from a local file path.

        series_id: path to the file
        kwargs: uploaded_file (Streamlit UploadedFile object, takes precedence)
        """
        uploaded_file = kwargs.get("uploaded_file")
        if uploaded_file is not None:
            df, _msg = load_uploaded_file(uploaded_file)
        else:
            df, _msg = load_csv_from_path(series_id)

        if start_date and hasattr(df.index, 'to_series'):
            df = df[df.index >= pd.Timestamp(start_date)]
        if end_date and hasattr(df.index, 'to_series'):
            df = df[df.index <= pd.Timestamp(end_date)]

        return df

    def check_status(self) -> tuple:
        return True, "File upload always available"
