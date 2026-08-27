# FCC Models

This directory tracks data files available on the FCC CVMFS repository.

## Submitting a new model or version

Create a YAML file (any name, e.g. `my-submission.yml`) with a `packages` list:

```yaml
packages:
  - package: my-onnx-model
    version: "1.0"
    source-location: http://example.com/my-onnx-model-1.0.root
  - package: another-model
    version: "2.3"
    source-location: http://example.com/another-model-2.3.onnx
```

Open a pull request. A workflow will automatically validate your submission and post a comment with the result.

**Rules:**
- The `summary_` prefix is reserved — do not use it for submission files.
- Each `package` + `version` combination must be unique across all submissions.
- All three fields (`package`, `version`, `source-location`) are required for every entry.

## What happens on merge

1. The action validates all entries (fails if any version already exists).
2. Each entry is appended to its `summary_<package>.yml` file.
3. Your submission file is deleted — the summary becomes the permanent record.
4. A GitHub Actions artifact is uploaded containing your original submission file.

## Summary files

`summary_<package>.yml` files are maintained automatically. Do not edit them by hand.
