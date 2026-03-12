# project_template

This template includes common configuration and settings for ALS Computing projects.

<!-- TREE START -->
<pre>
.
├── <a href="https://github.com/als-computing/project_template/blob/main/Dockerfile">Dockerfile</a>
├── <a href="https://github.com/als-computing/project_template/blob/main/README.md">README.md</a>
├── <a href="https://github.com/als-computing/project_template/tree/main/_tests">_tests</a>
│   └── <a href="https://github.com/als-computing/project_template/blob/main/_tests/test_example.py">test_example.py</a>
├── <a href="https://github.com/als-computing/project_template/tree/main/mkdocs">mkdocs</a>
│   ├── <a href="https://github.com/als-computing/project_template/tree/main/mkdocs/docs">docs</a>
│   │   ├── <a href="https://github.com/als-computing/project_template/blob/main/mkdocs/docs/about.md">about.md</a>
│   │   ├── <a href="https://github.com/als-computing/project_template/tree/main/mkdocs/docs/assets">assets</a>
│   │   │   ├── <a href="https://github.com/als-computing/project_template/blob/main/mkdocs/docs/assets/als_style.css">als_style.css</a>
│   │   │   └── <a href="https://github.com/als-computing/project_template/tree/main/mkdocs/docs/assets/images">images</a>
│   │   │       ├── <a href="https://github.com/als-computing/project_template/blob/main/mkdocs/docs/assets/images/doe_logo.png">doe_logo.png</a>
│   │   │       └── <a href="https://github.com/als-computing/project_template/blob/main/mkdocs/docs/assets/images/lbl_logo.png">lbl_logo.png</a>
│   │   ├── <a href="https://github.com/als-computing/project_template/blob/main/mkdocs/docs/index.md">index.md</a>
│   │   └── <a href="https://github.com/als-computing/project_template/blob/main/mkdocs/docs/test.md">test.md</a>
│   ├── <a href="https://github.com/als-computing/project_template/blob/main/mkdocs/mkdocs.yml">mkdocs.yml</a>
│   └── <a href="https://github.com/als-computing/project_template/tree/main/mkdocs/overrides">overrides</a>
│       ├── <a href="https://github.com/als-computing/project_template/tree/main/mkdocs/overrides/assets">assets</a>
│       │   └── <a href="https://github.com/als-computing/project_template/tree/main/mkdocs/overrides/assets/images">images</a>
│       │       └── <a href="https://github.com/als-computing/project_template/blob/main/mkdocs/overrides/assets/images/favicon.png">favicon.png</a>
│       └── <a href="https://github.com/als-computing/project_template/blob/main/mkdocs/overrides/main.html">main.html</a>
├── <a href="https://github.com/als-computing/project_template/blob/main/pytest.ini">pytest.ini</a>
├── <a href="https://github.com/als-computing/project_template/blob/main/requirements.txt">requirements.txt</a>
└── <a href="https://github.com/als-computing/project_template/tree/main/scripts">scripts</a>
    └── <a href="https://github.com/als-computing/project_template/blob/main/scripts/update_readme_tree.py">update_readme_tree.py</a>
</pre>
<!-- TREE END -->


## Features

Included in this template are a number of helpful things to get you started on the ground running.

### GitHub Actions `.github/workflows/build-app.yml`

Automate linting, pytest, and mkdocs when you push changes to GitHub.

### MkDocs

Create nice documentation with MkDocs and deploy it directly in your repository (Note: Your repository must be set to `public`).

### `.gitignore`

Already configured with a number of common files to ignore.

### `requirements.txt`

List of Python dependencies, such as flake8, pytest, and mkdocs.

### flake8

Lint your Python code for errors with flake8.

### PyTest

Write unit tests with PyTest and they will run when you submit a push to GitHub.

## LBNL Software Disclosure and Distribution

[Here is the official lab policy regarding software disclosure and distribution,](https://commons.lbl.gov/display/rpm2/Software+Disclosure+and+Distribution#SoftwareDisclosureandDistribution--1898802862) and below you will find a summarized version. It is general good practice to keep your projects marked as `private` until you properly disclose your software through the lab.

- **Purpose:**  
  Ensure DOE compliance by reporting all software intended for external distribution to the Intellectual Property Office (IPO).

- **Who Must Comply:**  
  Berkeley Lab software developers and affiliates (employees, faculty, and on-site collaborators).

- **When to Report:**  
  - Before distributing any new or modified software.
  - Exemptions: Already disclosed or minor updates (<25% change without added functionality).

- **Key Requirements:**  
  - **Submission:** Complete a Software Disclosure form prior to external distribution.
  - **Licensing:**  
    - Obtain appropriate license agreements through IPO.
    - Prefer permissive licenses (BSD, MIT) over proprietary or viral open source licenses (e.g., GNU GPL).
  - **Documentation:**  
    - Record third-party licenses, contributor information, and funding sources.
  - **Tracking:**  
    - If distributed via personal repositories or websites, track and report download/licensing metrics annually.

- **IPO Responsibilities:**  
  Review disclosures, secure DOE approvals, manage licensing agreements, and maintain records.

- **Contact:**  
  For questions, reach out to the Licensing Manager at [ipo@lbl.gov](mailto:ipo@lbl.gov).

