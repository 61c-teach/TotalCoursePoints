from setuptools import setup

with open("README.md") as f:
    readme = f.read()

setup(name='TotalCoursePoints',
      version='0.1',
      description="This is the backend which is meant to make generating student grades easier.",
      long_description=readme,
      author='Stephan Kaminsky',
      author_email='skaminsky115@berkeley.edu',
      license='MIT',
      packages=['TotalCoursePoints'],
      install_requires=["numpy", "pandas", "pytz", "gspread", "oauth2client"],
      )