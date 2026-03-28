# How to describe your Tool?

One of the main criteria for the tool-registry (https://dev.tools-registry.eosc-data-commons.eu/docs) is to facilitate matchmaking between dataset and analytical tool. For this reason, tools need to be describe adequitally enough so that the matchmaker can reason about the tools. WE have a minimum schema to do this which can be extended to accommodate different types of tools. 
The minimum schema is the following:

```yaml
{
  "uri": "string",
  "name": "string",
  "version": "string",
  "location": "string",
  "description": "string",
  "archetype": "string",
  "input_file_formats": [],
  "output_file_formats": [],
  "input_file_descriptions": [],
  "output_file_descriptions": [],
  "keywords": [],
  "tags": [],
  "license": "string",
  "raw_metadata": {},
  "metadata_schema": {},
  "metadata_version": "",
  "metadata_type": "",
}
```

The fields are defined as follows:

- `uri`: A unique identifier for the tool, typically a URL or a UUID.
- `name`: The name of the tool.
- `version`: The version of the tool.
- `location`: The location where the tool can be accessed or downloaded.
- `description`: A description of the tool and its functionality. This will be used in embeddings and for matchmaking so it should use keywords that are relevant for the tool.
- `archetype`: The archetype of the tool, which can be used to categorize the tool based on its functionality or domain. This can be your choice or use one of the predefined archetypes ["galaxy_workflow", "vip_app_boutique"]
- `input_file_formats`: A list of file formats that the tool can accept as input. E.g. ["csv", "tsv", "json", "xml"]
- `output_file_formats`: A list of file formats that the tool can produce as output. E.g. ["csv", "tsv", "json", "xml"]
- `input_file_descriptions`: A list of descriptions for the input files that the tool can accept. This can replace th input_file_formats field if you want to be more specific about the input files. E.g. ["a csv file with the following columns: id, name, age", "a json file with the following structure: {\"id\": \"string\", \"name\": \"string\", \"age\": \"integer\"}"]
- `output_file_descriptions`: A list of descriptions for the output files that the tool can produce. This can replace the output_file_formats field if you want to be more specific about the output files.
- `keywords`: A list of keywords that are relevant for the tool. This will be used in embeddings and for matchmaking so it should use keywords that are relevant for the tool.
- `tags`: A list of tags that can be used to categorize the tool. This is meant to filter searches so could include things like usecase names and general categories.
- `license`: The license under which the tool is distributed. E.g. "MIT", "GPL-3.0", "Apache-2.0"
- `raw_metadata`: A field to store any additional metadata about the tool that may be relevant for matchmaking or other purposes. This can be used to store any additional information about the tool that may be relevant for matchmaking or other purposes. E.g. {"author": "John Doe", "publication": "https://doi.org/10.1234/example"}
- `metadata_schema`: A field to store the schema of the metadata. This can be used to validate the metadata and ensure that it is in the correct format. E.g. {"type": "object", "properties": {"author": {"type": "string"}, "publication": {"type": "string"}}}
- `metadata_version`: A field to store the version of the metadata schema. This can be used to ensure that the metadata is compatible with the schema. E.g. "1.0"
- `metadata_type`: A field to store the type of metadata. This can be used to categorize the metadata and ensure that it is relevant for matchmaking or other purposes. E.g. "a_galaxy_workflow", "a_vip_app_boutique"
