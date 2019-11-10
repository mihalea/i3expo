from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

setup(name='i3expo',
      version='0.1',
      description='Provide a workspace overview for i3wm',
      long_description=long_description,
      url='https://github.com/mihalea/i3expo',
      author='Mircea Mihalea, Josh Walls',
      author_email='mircea@mihalea.ro, me@joshwalls.co.uk',
      license='GPL',
      zip_safe=False,
      #install_requires=requirements,
      #setup_requires=requirements,
      py_modules=['i3expod'],
      entry_points={
          'console_scripts': [
              'i3expo=i3expod:main'
          ]
      })
