import argostranslate.package

# Update package index
argostranslate.package.update_package_index()
available_packages = argostranslate.package.get_available_packages()

# Install English -> Malayalam
package = next(
    (pkg for pkg in available_packages 
     if pkg.from_code == "en" and pkg.to