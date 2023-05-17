from typing import Mapping

import pandas as pd
import pandera as pa


def inital_data_mapping_plan(uploaded_files: list[str], description_dict: Mapping[str, str]) -> Mapping[str, str]:
    # Initialize an empty dictionary to store the output
    output_dict = {}

    # Loop through all the files
    for uploaded_file in uploaded_files:
        # Read the file into a pandas DataFrame
        df = pd.read_csv(uploaded_file.file.path)

        # Loop through the columns in the DataFrame
        for column in df.columns:
            # If the column is not already in the dictionary, add it
            if column not in output_dict:
                output_dict[column] = "This column will be generated from the '{}' field in the '{}' file.".format(column, uploaded_file.file.name)

    return output_dict


def generate_description_dict(df):
    # Replace this with your actual implementation
    description_dict = {column: "Description for " + column for column in df.columns}
    return description_dict

def generate_pandera_schema(df):
    # Replace this with your actual implementation
    pandera_schema = pa.infer_schema(df).to_json()
    return pandera_schema

def execute_mapping_plan(files: list[str], mapping_plan: Mapping[str, str], description_dict: Mapping[str, str]) -> pd.DataFrame:
    df = pd.concat([pd.read_csv(file) for file in files])
    return df

