# GitHub CSharpier Linter Action

<div align="center">

[![GitHub repo](https://img.shields.io/badge/GitHub-guibranco%2Fgithub--csharpier--linter--action-green.svg?style=flat-square&logo=github)](https://github.com/guibranco/github-csharpier-linter-action)
[![GitHub last commit](https://img.shields.io/github/last-commit/guibranco/github-csharpier-linter-action?color=green&logo=github&style=flat-square&label=Last%20commit)](https://github.com/guibranco/github-csharpier-linter-action)
[![GitHub license](https://img.shields.io/github/license/guibranco/github-csharpier-linter-action?color=green&logo=github&style=flat-square&label=License)](https://github.com/guibranco/github-csharpier-linter-action)
![CI](https://github.com/guibranco/github-csharpier-linter-action/actions/workflows/ci.yml/badge.svg)
[![wakatime](https://wakatime.com/badge/github/guibranco/github-csharpier-linter-action.svg)](https://wakatime.com/badge/github/guibranco/github-csharpier-linter-action)

</div>

## 📋 Overview

A **GitHub Action** to automatically check and enforce **C# code formatting** using **[CSharpier](https://csharpier.com/)**. This action helps maintain clean code by running formatting checks and posting annotations, job summaries, and PR comments when issues are detected.

## 🛠 Features

- **Automatic formatting check**: Uses `dotnet csharpier check .` to validate the formatting of all C# files.
- **Job summary**: Uploads a neat, easy-to-read summary in the GitHub Actions interface.
- **Inline annotations**: Adds warnings in the code where formatting is incorrect.
- **PR comments**: Posts a comment on the pull request with the list of issues detected.

## 🧩 Usage

You can use this action in your workflows by referencing it as a reusable workflow:

```yaml
jobs:
  linter-check:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - name: CSharpier Linter
        uses: guibranco/github-csharpier-linter-action@v1.0.5
```

## ⚡ Requirements

- **C#** files should be part of your repository.
- Make sure your repository has `.cs` files, `.csproj`, or similar files that are relevant to the format.

## 📝 Outputs

- **Job summary**: Available in the PR Checks section, clearly summarizing the formatting issues.
- **Annotations**: Warning annotations are placed on the lines where formatting issues are found.
- **PR Comments**: An easy-to-read comment posted directly on the PR.

## 💡 Example Workflow

Here’s an example workflow that uses this action:

```yaml
name: Linter check

on:
  workflow_dispatch:
  pull_request:

jobs:
  linter-check:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - name: CSharpier Linter
        uses: guibranco/github-csharpier-linter-action@v1.0.5
```

## 🔧 How It Works

1. **Setup .NET**: Ensures that .NET SDK is installed.
2. **Run CSharpier**: Runs `dotnet csharpier check .` and checks for any formatting issues.
3. **Create Annotations and PR Comments**: If issues are found, the action creates inline annotations, a job summary, and a comment on the PR.

## 🛠 Development

To contribute to this action:
- Clone the repository and test locally.
- Make sure to follow best practices for creating GitHub Actions.

---

### 🚀 Installation & Contribution

- Clone this repo to use in your own workflows.
- Feel free to open issues or submit pull requests to improve the action!

## 🏆 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
