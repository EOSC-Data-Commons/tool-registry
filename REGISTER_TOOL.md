# Registering a Tool

Tools should first be published in one of the supported public repositories:

* [WorkflowHub](https://workflowhub.eu/)
* [GitHub](https://github.com/)
* [Zenodo](https://zenodo.org/)
* [bio.tools](https://bio.tools/)

The registry harvests metadata from these sources.

## WorkflowHub

Publish the workflow or tool in WorkflowHub.

No additional registration step is required if WorkflowHub is harvested automatically.

Example:

```text
https://workflowhub.eu/workflows/123
```

## bio.tools

Publish the tool in bio.tools.

No additional registration step is required if bio.tools is harvested automatically.

Example:

```text
https://bio.tools/my-tool
```

## GitHub

Publish the software in a public GitHub repository.

Example:

```text
https://github.com/example/my-tool
```

Then register the repository URL with the Tool Registry:

```bash
curl -X POST https://tool-registry-api.eosc-data-commons.dansdemo.nl/sources \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://github.com/example/my-tool"
  }'
```


## Zenodo

Publish the software as a Zenodo record.

Example:

```text
https://zenodo.org/records/123456
```

Then register the Zenodo record URL:

```bash
curl -X POST https://tool-registry-api.eosc-data-commons.dansdemo.nl/sources \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://zenodo.org/records/123456"
  }'
```

## Summary

```text
WorkflowHub
    └── publish tool
        └── harvested automatically

bio.tools
    └── publish tool
        └── harvested automatically

GitHub
    └── publish repository
        └── POST repository URL to Tool Registry

Zenodo
    └── publish software record
        └── POST record URL to Tool Registry
```

## Want to a add a new repository?

Open an issue in the [Tool Harvester GitHub repository](https://github.com/eosc-data-commons/toolmeta-harvester/issues) to request a new repository to be added to the registry.

