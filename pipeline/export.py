
import os
import pandas as pd

def ensure_dir(path:str):
    os.makedirs(path, exist_ok=True)

def write_csv(df: pd.DataFrame, out_path: str, index: bool=False):
    ensure_dir(os.path.dirname(out_path))
    df.to_csv(out_path, index=index)

def write_multi_csv(tables: dict, out_dir: str, prefix: str):
    ensure_dir(out_dir)
    for sheet, df in tables.items():
        safe = str(sheet).replace(" ", "_").replace("/", "_")
        df.to_csv(os.path.join(out_dir, f"{prefix}__{safe}.csv"), index=False)
