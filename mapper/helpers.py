import json
from typing import Mapping, Optional, Union

import pandas as pd
import pandera as pa
from django.conf import settings
from langchain import LLMChain, OpenAI, PromptTemplate
from pydantic import BaseModel
from marvin import ai_fn, ai_model

PARSED_FROM_UNSTRUCTURED_TEXT = "parsed_from_text"


class FileFieldReference(BaseModel):
    """
    A class to store a reference to a file field
    """
    file_name: str
    field_name: str


class Categorisation(BaseModel):
    """
    A class to store a plan for parsing from an unstructured format to a structured format.
    file_fields is a list of references to the file fields that will be used to parse the data.
    parsed_value_options is a string that describes the options for the parsed value.
    For example, if we want to parse a colour and the options are "red", "green", and "blue", the parsed_value_options
    would be "red, green, blue".
    For example, if we want to parse a colour and we allow any color as an option, the parsed_value_options would be
    "any color".
    """
    file_fields: list[FileFieldReference]
    parsed_value_options: str

class StructuredToStructuredParsingPlan(BaseModel):
    """
    A class to store a plan for parsing from a structured format to another structured format.
    formula is a human-readable formula that describes the parsing plan with references to the file fields.
    For example, if we want to parse the column "name" from the file "file1.csv" and the column "age" from the file
    "file2.csv", the formula would be "'file1.csv'.'name', 'file2.csv'.'age'".
    if we wanted to concatenate the two columns, the formula would be "'file1.csv'.'name' 'file2.csv'.'age'"
    """
    file_fields: list[FileFieldReference]
    formula: str

@ai_model
class ColumnParsingPlan(BaseModel):
    """
    A class to store a plan for parsing a column.
    """
    column_name: str
    parsing_plan: Union[Categorisation, StructuredToStructuredParsingPlan]

# @ai_model
class ParsingPlan(BaseModel):
    """
    A class to store a plan for parsing from one format to another.
    """
    plan: Mapping[str, Union[Categorisation, StructuredToStructuredParsingPlan]]

# class Category(BaseModel):
#     """
#     A class to store a category.
#     """
#     name: str
#     description: Optional[str]
#
#     def toJSON(self):
#         return json.dumps(self, default=lambda o: o.__dict__,
#                           sort_keys=True, indent=4)

class Category(BaseModel):
    """
    A class to store a category.
    """
    value: str


@ai_model
class Categories(BaseModel):
    """
    A class to store a list of categories.
    """
    categories: Optional[list[Category]]

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=4)

def inital_data_mapping_plan(uploaded_files: list[str], description_dict: Mapping[str, str], categories_dict: Mapping[str, Union[str, list[str]]]) -> Mapping[str, str]:
    # get the first three examples of each file and store them in a dict where the keys are the name of the files
    # and the values are the first three examples of each file
    examples = {}
    for uploaded_file in uploaded_files:
        df = pd.read_csv(uploaded_file)
        file_name = uploaded_file.split("/")[-1]
        examples[file_name] = df.head(3)

    # convert this to a paragraph where the name of the file precedes the examples. Then we add a markdown table with
    # the header and the first three examples of each file
    examples_str = ""
    for file_name, df in examples.items():
        examples_str += f"{file_name}\n"
        examples_str += df.to_markdown()
        examples_str += "\n\n"

    # print(examples_str)

    template = f"""Question:
    My files are as follows:
    {examples_str}

    """

    # Get files to parse categories from
    categories_template = template + """
    I would like to parse the field {field} which has the description {description}. 
    The categories for the field are as follows: {categories}.
    
    We would like to get the list of fields where this information can be parsed from.
    
    Example 1: 
    Question: We want to parse the field `health_condition` of a person. The possible values are "cancer", "diabetes", "heart disease".
     Suppose we have a column named "description" that describes the health condition of a person in "file1.csv" and the column "health_condition" in "file2.csv".
    Answer: file1.description, file2.health_condition
    
    Answer: 
    """

    formula_template = template + """
    In my target dataframe, I would like to parse to a column named {column} from the files. This is a description of the column: {description}. 
    
    Example 1: if we want to parse the column "name" from the file "file1.csv" and the column "age" from the file
    "file2.csv", the formula would be "file1.name, file2.age".
    Example 2: if we wanted to concatenate the two columns, the formula would be "file1.name file2.age"
    Example 3: if we wanted to parse the column "health_condition" from the file "file1.csv", but we can only infer it
    from a column(s) with unstructured text, the formula would be "parsed from file1.unstructured_column, file1.other_unstructured_column"

    Answer: Formula: """

    formula_prompt = PromptTemplate(template=formula_template, input_variables=["column", "description"])
    categories_prompt = PromptTemplate(template=categories_template, input_variables=["field", "description", "categories"])


    llm = OpenAI(model_name="gpt-3.5-turbo", temperature=0.0)
    formula_llm_chain = LLMChain(prompt=formula_prompt, llm=llm)
    categories_llm_chain = LLMChain(prompt=categories_prompt, llm=llm)
    # # @ai_fn
    # def _get_column_parsing_plan_description(column_parsing_plan: ColumnParsingPlan) -> str:
    #     # """
    #     # This function takes a column parsing plan and returns a human-readable description of the plan.
    #     # """
    #     def file_field_str(file_field: FileFieldReference) -> str:
    #         return f"'{file_field.file_name}'.'{file_field.field_name}'"
    #     if isinstance(column_parsing_plan.parsing_plan, Categorisation):
    #         return f"Parsed from {', '.join([file_field_str(file_field) for file_field in column_parsing_plan.parsing_plan.file_fields])}. Values: {column_parsing_plan.parsing_plan.parsed_value_options}"
    #     elif isinstance(column_parsing_plan.parsing_plan, StructuredToStructuredParsingPlan):
    #         return f"{column_parsing_plan.parsing_plan.formula}"
    #
    # mapping_plan = {}
    # mapping_plan_description = {}
    # for field, description in description_dict.items():
    #     prompt = f"""I have multiple files with different columns.
    #         My files are as follows:
    #         {examples_str}
    #
    #         I would like to parse a field named {field} from the files. This is a description of the field: {description}
    #         """
    #     mapping_plan[field] = ColumnParsingPlan(prompt)
    #     mapping_plan_description[field] = _get_column_parsing_plan_description(mapping_plan[field])
    #
    # return mapping_plan_description
    mapping_plan = {}
    for field, description in description_dict.items():
        if field in categories_dict:
            categories = categories_dict[field]
            list_of_files = categories_llm_chain.run(field=field, description=description, categories=categories)
            mapping_plan[field] = "Parsed from " + list_of_files
        else:
            mapping_plan[field] = formula_llm_chain.run(column=field, description=description)

    return mapping_plan



    # return mapping_plan


    # # Initialize an empty dictionary to store the output
    # output_dict = {}
    #
    # # Loop through all the files
    # for uploaded_file in uploaded_files:
    #     # Read the file into a pandas DataFrame
    #     df = pd.read_csv(uploaded_file.file.path)
    #
    #     # Loop through the columns in the DataFrame
    #     for column in df.columns:
    #         # If the column is not already in the dictionary, add it
    #         if column not in output_dict:
    #             output_dict[column] = "This column will be generated from the '{}' field in the '{}' file.".format(column, uploaded_file.file.name)
    #
    # return output_dict

llm = OpenAI(model_name="gpt-3.5-turbo", temperature=0.0)

def generate_description_dict(df):
    # Replace this with your actual implementation
    # print("template", template)
    description_dict = {}
    categories_dict = {}
    df_markdown = df.head(3).to_markdown()
    for column in df.columns:
        template = f"""This is a sample of my dataframe:
                    {df_markdown}

                Write a succinct description of the column {column}. Don't include superfluous information. Don't mention any reference to the dataframe or dataset.
                Answer: The column {column} 
            """
        description_dict[column] = llm(template)
        # llm_chain = LLMChain(prompt=PromptTemplate(template=template), llm=llm)
        template = f"""
            These are the values of a column in my dataframe:
            {df[column]}
            
            Are there categories in this data as it is? Answer with "yes" or "no".  
            
            Example 1: 
                Question: ['Clarence', 'Erika', 'Juan', 'Terry', 'Joyce', 'Hilary']
                Answer: no. Given the context, these are names of people and not categories.
                
                Question: ['05/17/1964', '05/17/2014', '05/17/2003', '05/17/1925', '05/17/1954', '05/17/1986', '05/17/1936']
                Answer: no. These are specific dates and there are no categories in this data as it is.
            
            Answer: 
        """
        answer = llm(template)
        if not answer.lower().startswith('no'):
            categories = Categories(f"{df[column]}")
            if categories.categories:
                categories = (list(map(lambda x: x.value, categories.categories)))
                categories_dict[column] = categories
        # categories_dict[column] = Categories(f"{df[column]}")
        # description_dict[column] = ", ".join(list(map(lambda x: x.name, categories_dict[column].categories)))

        # description_dict[column] = llm(template)

    # description_dict = {column: "Description for " + column for column in df.columns}
    return description_dict, categories_dict

def generate_pandera_schema(df):
    # Replace this with your actual implementation
    pandera_schema = pa.infer_schema(df).to_json()
    return pandera_schema

def execute_mapping_plan(files: list[str], mapping_plan: Mapping[str, str], description_dict: Mapping[str, str], categories_dict: Mapping[str, Union[str, list[str]]]) -> pd.DataFrame:

    examples = {}
    df = pd.DataFrame()
    code_to_exec = [
        "df = pd.DataFrame()",
    ]
    for uploaded_file in files:
        df = pd.read_csv(uploaded_file)
        file_name = uploaded_file.split("/")[-1]
        examples[file_name] = df.head(3)
        file_name_df = file_name.split(".")[0] + "_df"
        code_to_exec.append(f"{file_name_df} = pd.read_csv('{uploaded_file}')")

    inital_code_to_exec = "\n".join(code_to_exec)

    # convert this to a paragraph where the name of the file precedes the examples. Then we add a markdown table with
    # the header and the first three examples of each file
    examples_str = ""
    for file_name, df in examples.items():
        examples_str += f"{file_name}\n"
        examples_str += df.to_markdown()
        examples_str += "\n\n"



    for column, formula in mapping_plan.items():
        # if column in categories_dict:
        #     continue
        # here we have to convert the
        # if column in categories_dict:
        #     mapping_plan[column][0] = mapping_plan[column][0].removeprefix("Parsed from ")
        template = f"""These are the files I have:
                {examples_str}
                
                Write a single-line of code to parse the column `{column}` from the files. Don't write the entire parsing plan, just the code to parse the column.
                You can refer to a file by file_name_df. For example, if the file is named 'my_file.csv', you can refer to it as 'my_file_df'.
                Assume we have a target dataframe called df.
                
                No column should start with the words "Parsed from". Neither should the name of the file be mentioned in the name of the column.
                
                This is the existing code:
                {inital_code_to_exec}
                
                The formula to parse the column `{column}` is: {mapping_plan[column]}
                
                Example: 
                    Question: The formula to parse the column abcd is: file1.foo + file2.bar
                    Answer: df['abcd'] = file1_df['foo'] + file2_df['bar']
                
                Answer: The single-line of code to parse the column `{column}` is:
            """
        code_to_exec.append(llm(template))

    code_to_exec.append("from marvin.ai_functions.data import map_categories, categorize")
    for column, categories in categories_dict.items():
        # template = f"""These are the files I have:
        #                 {examples_str}
        #
        #                 Write a single-line of code to parse the column {column} from the files. Don't write the entire parsing plan, just the code to parse the column.
        #                 You can refer to a file by file_name_df. For example, if the file is named 'my_file.csv', you can refer to it as 'my_file_df'.
        #                 Assume we have a target dataframe called df.
        #
        #                 The formula to parse the column {column} is: {column_to_parse_formula}
        #
        #                 Example:
        #                     Question: The formula to parse the column abcd is: file1.foo + file2.bar
        #                     Answer: df['abcd'] = file1_df['foo'] + file2_df['bar']
        #
        #                 Answer: The single-line of code to parse the column {column} is:
        #             """
        # code_to_exec.append(llm(template))
        if isinstance(categories, str):
            code_to_exec.append(f"df['{column}'] = categorize(df['{column}'], description='{categories}')")
        else:
            code_to_exec.append(f"df['{column}'] = map_categories(df['{column}'], categories={categories})")

    code_to_exec = "\n".join(code_to_exec)
    print(code_to_exec)

    exec(code_to_exec)








    # template = f"""This is a sample of my dataframe:
    #                     {df_markdown}
    #
    #                 Write a succinct description of the column {column} in active voice.
    #                 Answer:
    #             """
    # # llm_chain = LLMChain(prompt=PromptTemplate(template=template), llm=llm)
    # description_dict[column] = llm(template)
    #
    # df = pd.concat([pd.read_csv(file) for file in files])
    return df

def run_data_quality_checks(df: pd.DataFrame, schema: pa.DataFrameSchema) -> Mapping[str, str]:
    # Replace this with your actual implementation
    # errors = {column: "Error for " + column for column in df.columns}
    # return errors
    try:
        schema.validate(df)
    except pa.errors.SchemaError as e:
        errors = {column: str(e) for column in df.columns}
        return errors
    return {}

def apply_transformations_to_df(orig_df: pd.DataFrame, transformations: Mapping[str, str]) -> pd.DataFrame:
    # Replace this with your actual implementation
    df = pd.DataFrame()
    code_to_exec = [
        "df = pd.DataFrame()",
        "df = orig_df"
    ]
    example_df = orig_df.head(3).to_markdown()
    for column, formula in transformations.items():
        if not formula:
            continue
        template = f"""This is a sample of my dataframe:
                        {example_df}
                    
                        Write a single-line of code to transform the column `{column}`. Don't write the entire transformation plan, just the code to transform the column.
                        Assume we have a target dataframe called df.
                        
                        The transformation required for column `{column}` is: {formula}
                        
                        Example: 
                            Question: The transformation required for column abcd is: normalize by the maximum value
                            Answer: df['abcd'] = df['abcd'] / df['abcd'].max()
                        
                        Answer: The single-line of code to transform the column `{column}` is:
                    """
        code_to_exec.append(llm(template))

    code_to_exec = "\n".join(code_to_exec)
    print(code_to_exec)

    exec(code_to_exec)
    return df