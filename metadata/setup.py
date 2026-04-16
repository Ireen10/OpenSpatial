from setuptools import setup, find_packages


setup(
    name="openspatial-metadata",
    version="0.0.1",
    description="Metadata subproject: config-driven ingestion, JSON/JSONL IO, and utilities (v0).",
    package_dir={"": "src"},
    packages=find_packages("src"),
    package_data={"openspatial_metadata": ["viz/static/index.html"]},
    include_package_data=True,
    install_requires=[
        "pydantic>=1.8,<2",
        "pyyaml",
    ],
    extras_require={"dev": ["pytest", "Pillow>=9.0"]},
    entry_points={
        "console_scripts": [
            "openspatial-metadata=openspatial_metadata.cli:main",
            "openspatial-metadata-viz=openspatial_metadata.viz.cli:main",
        ]
    },
)

