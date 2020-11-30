from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# This collects all dynamically imported scrapy modules and data files.
hiddenimports = (collect_submodules('peewee_migrate')
)
datas = collect_data_files('peewee_migrate')