import os
import shutil


def main():
    """Copy conf and data/processed directories to the tri4plads package."""
    # Define source and destination paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    conf_src = os.path.join(current_dir, os.pardir, "conf")
    data_src = os.path.join(current_dir, os.pardir, "data", "processed")
    package_dest = os.path.join(current_dir, os.pardir, "src", "tri4plads")

    # Copy conf to tri4plads
    conf_dest = os.path.join(package_dest, "conf")
    if not os.path.exists(conf_dest):
        shutil.copytree(conf_src, conf_dest)

    # Copy data/processed to tri4plads
    data_dest = os.path.join(package_dest, "data", "processed")
    os.makedirs(os.path.dirname(data_dest), exist_ok=True)
    if not os.path.exists(data_dest):
        shutil.copytree(data_src, data_dest)
