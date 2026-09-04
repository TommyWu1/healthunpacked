from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            "healthunpacked._scan",
            sources=["src/healthunpacked/_scan.c"],
            extra_compile_args=["-O2", "-Wall", "-Wextra"],
        )
    ]
)
