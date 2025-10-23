from typing import TypeVar, Type, Optional, List, Dict, Any
import pandas as pd
from pydantic import BaseModel, ValidationError, Field, model_validator, 
from pydantic_core import ErrorDetails
import logging
# Define a generic type for Pydantic models
PydanticModel = TypeVar("PydanticModel", bound=BaseModel)


# def validate_df_with_pydantic(
#     df: pd.DataFrame, model: Type[PydanticModel]
# ) -> pd.DataFrame:
#     """
#     Validates a DataFrame against a Pydantic model.

#     Args:
#         df: The pandas DataFrame to validate.
#         model: The Pydantic model class to validate each row against.

#     Returns:
#         A new DataFrame with validated and potentially coerced data.

#     Raises:
#         ValidationError: If any row fails validation.
#         ValueError: If the input is not a DataFrame or is empty.
#     """
#     if not isinstance(df, pd.DataFrame):
#         raise ValueError("Input must be a pandas DataFrame.")
#     if df.empty:
#         raise ValueError("Input DataFrame is empty.")
#     # Ensure the column names of the dataframe are strings
#     df.columns = df.columns.astype(str)
#     try:
#         # Convert, validate, and dump back to dicts
#         validated_data = [
#             model(**{str(k): v for k, v in row.items()}).model_dump()
#             for row in df.to_dict(orient="records")
#         ]
#         # Create a new DataFrame from validated data
#         return pd.DataFrame(validated_data)
#     except ValidationError as e:
#         print(f"DataFrame validation failed against model '{model.__name__}':")
#         # You might want to provide more context about *which* rows failed
#         raise e
#     except Exception as e:
#         print(f"An unexpected error occurred during validation: {e}")
#         raise e

class LongData(BaseModel):
    Temperature: float = Field(..., description="Temperature in Celsius.")
    value: float = Field(..., description="Measured value at the given temperature and well.")
    ligand: str = Field(..., description="Ligand identifier (e.g., 'LigandA').")
    protein: str = Field(..., description="Protein identifier (e.g., 'ProteinX').")
    buffer: str = Field(..., description="Buffer condition (e.g., 'Buffer1').")
    

class LongDataRaw(LongData):
    well: str = Field(..., description="Well identifier (e.g., 'A1', 'B2').")

    well_uqcond: str = Field(
        ...,
        description="Unique Combination of well ligand, protein, and buffer conditions.",
    )

    
class LongDataAvg(LongData):
    uq_cond: Optional[str] = Field(
        None,
        description="Unique condition identifier combining ligand, protein, and buffer.",
    )
    


class WideDataNumeric(BaseModel):
    """
    Represents a row in a DataFrame.
    It has fixed 'id' and 'category' fields, and allows for any number
    of additional dynamic fields, which are expected to be numeric.
    """

    # --- Fixed fields ---
    Temperature: float = Field(..., description="Temperature in Celsius.")
 
    # --- Configuration to allow extra fields ---
    # This tells Pydantic to accept fields not explicitly defined above.
    # These extra fields will be stored in `self.model_extra` and included in `model_dump()`.
    model_config = {"extra": "allow"}

    # --- Validator for dynamic/extra fields ---
    @model_validator(mode="after")
    def check_dynamic_features_are_numeric(self) -> "WideDataNumeric":
        """
        Validates that all dynamically added fields (extras) are numeric (int or float).
        This validator runs after the initial parsing of known fields.
        """
        if self.model_extra:  # self.model_extra contains the dict of dynamic fields
            for field_name, value in self.model_extra.items():
                if not isinstance(value, float):
                    # Raise a ValueError; Pydantic will catch this and incorporate it
                    # into its standard ValidationError structure.
                    raise ValueError(
                        f"Dynamic feature '{field_name}' must be numeric (int or float), "
                        f"but got type {type(value).__name__} with value '{value}'."
                    )
        return self

class WideDataNoBase(WideDataNumeric):
    
    @model_validator(mode="after")
    def check_no_col_names_contain_npc(self) -> "WideDataNoBase":
        """
        Validates that no column names contain 'npc'.
        This validator runs after the initial parsing of known fields.
        """
        
        if self.model_extra:
            for field_name in self.model_extra.keys():
                if "NPC" in field_name.lower():
                    raise ValueError(
                        f"Column name '{field_name}' contains 'NPC', which should have been removed by this stage."
                    )
        return self
    
class WideDataMinMax(WideDataNoBase):
    
    @model_validator(mode="after")
    def check_min_max_columns(self) -> "WideDataMinMax":
        """checks that all columns except Temp are between 0 and 1, and that Temp is NOT between 0 and 1."""
        if self.model_extra:
            for field_name, value in self.model_extra.items():
                if not (0 <= value <= 1):
                    raise ValueError(
                        f"Column '{field_name}' must be between 0 and 1, but got {value}."
                    )
        if self.Temperature <1:
            logging.warning(
                f"Temperature '{self.Temperature}' is less than 1, which is unusual for this context."
            )
        return self
    
class LongDataMinMax(LongDataAvg):
    @model_validator(mode="after")
    def check_min_max_columns(self) -> "LongDataMinMax":
        """checks that all columns except Temp are between 0 and 1, and that Temp is NOT between 0 and 1."""
        if not (0 <= self.value <= 1):
            raise ValueError(
                f"Value '{self.value}' must be between 0 and 1, but got {self.value}."
            )
        if self.Temperature < 1:
            logging.warning(
                f"Temperature '{self.Temperature}' is less than 1, which is unusual for this context."
            )
        return self
    
class LongDataDT(LongDataAvg):
    # how to validate this?
    pass

class LongDataDTMinMax(LongDataDT):
    pass

class MinTempData(BaseModel):
    # include convert to float
    pass



class LayoutDynamicData(BaseModel):
    """
    Represents a row in a DataFrame.
    It has fixed 'id' and 'category' fields, and allows for any number
    of additional dynamic fields, which are expected to be numeric.
    """

    # --- Fixed fields ---
    well: str = Field(..., description="Well identifier (e.g., 'A1', 'B2').")


    # --- Configuration to allow extra fields ---
    # This tells Pydantic to accept fields not explicitly defined above.
    # These extra fields will be stored in `self.model_extra` and included in `model_dump()`.
    model_config = {"extra": "allow"}

    # --- Validator for dynamic/extra fields ---
    @model_validator(mode="after")
    def check_dynamic_features_are_str(self) -> "LayoutDynamicData":
        """
        Validates that all dynamically added fields (extras) are str
        This validator runs after the initial parsing of known fields.
        """
        if self.model_extra:  # self.model_extra contains the dict of dynamic fields
            for field_name, value in self.model_extra.items():
                if not isinstance(value, (str)):
                    # Raise a ValueError; Pydantic will catch this and incorporate it
                    # into its standard ValidationError structure.
                    raise ValueError(
                        f"Dynamic feature '{field_name}' must be numeric (int or float), "
                        f"but got type {type(value).__name__} with value '{value}'."
                    )
        return self

def validate_df_dynamic_model(
    df: pd.DataFrame, model_class: Type[BaseModel]
) -> pd.DataFrame:
    """
    Validates each row of a pandas DataFrame against the provided Pydantic model.

    Args:
        df: The pandas DataFrame to validate.
        model_class: The Pydantic model class to use for validation.

    Returns:
        A new pandas DataFrame containing the validated and potentially coerced data.

    Raises:
        TypeError: If the input 'df' is not a pandas DataFrame.
        ValidationError: If any row in the DataFrame fails validation against the model.
                         The raised error will contain details for all failing rows.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame.")

    if df.empty:
        print(
            "Warning: Input DataFrame is empty. Returning an empty DataFrame based on model fields."
        )
        # Create an empty DataFrame with columns based on the model's known fields.
        # Dynamic columns aren't known at this stage for an empty input.
        return pd.DataFrame(columns=list(model_class.model_fields.keys()))

    validated_rows_data: List[Dict[str, Any]] = []
    all_error_details: List[ErrorDetails] = (
        []
    )  # To collect Pydantic's ErrorDetail dicts

    # Ensure DataFrame columns are strings for **row unpacking, though model_validate is safer
    df.columns = df.columns.astype(str)

    for idx, row_dict in enumerate(df.to_dict(orient="records")):
        try:
            # Use model_validate for Pydantic v2
            validated_model_instance = model_class.model_validate(row_dict)
            # model_dump() will include extra fields by default if extra='allow'
            # It also handles alias generation, exclude_none, etc., if configured.
            validated_rows_data.append(validated_model_instance.model_dump())
        except ValidationError as e:
            # e.errors() returns a list of ErrorDetail dictionaries.
            # We prepend the DataFrame row index to the 'loc' (location)
            # of each error for better context.
            for error_detail in e.errors():
                current_loc = error_detail.get("loc", ())
                # Ensure current_loc is a tuple before prepending
                if not isinstance(current_loc, tuple):
                    current_loc = (current_loc,)
                error_detail["loc"] = (f"row_{idx}",) + current_loc
                all_error_details.append(error_detail)

    if all_error_details:
        # If there were any errors, construct and raise a single ValidationError
        # containing all collected error details from all rows.
        # The second argument to ValidationError is the model class itself.
        raise ValidationError(all_error_details, model_class)

    # If all rows are valid, create a new DataFrame from the validated data.
    return pd.DataFrame(validated_rows_data)
