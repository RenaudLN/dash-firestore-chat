from setuptools import setup, find_packages

setup(
    name="Dash Firestore Chat",
    version="0.1.0",
    author="Renaud Lainé",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "dash",
        # Until PR #145 is merged to the main dash-auth repo
        "dash-auth @ git+https://github.com/blunomy/dash-auth.git@feature/oidc",
        "dash-iconify",
        "dash-mantine-components",
        "dash-socketio",
        "firebase-admin",
        "flask",
        "flask-socketio",
        "google-cloud-firestore",
    ],
)
