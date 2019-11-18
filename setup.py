import setuptools

with open('README.md') as f:
    long_description = f.read()

setuptools.setup(name='i3expo',
      version='1.0',
      description='Provide a workspace overview for i3wm',
      long_description=long_description,
      url='https://github.com/mihalea/i3expo',
      author='Mircea Mihalea',
      author_email='mircea@mihalea.ro',
      license='GPL',
      zip_safe=False,
      # install_requires=requirements,
      # setup_requires=requirements,
      include_package_data=True,
      packages=setuptools.find_packages(),
      entry_points={
          'console_scripts': [
              'i3expo-daemon=i3expo.daemon:main',
              'i3expo=i3expo.client:main'
          ]
      })
