from services.inventory import Inventory
from services.fetcher import DriveFetcher

def main():
    driveFetcher = DriveFetcher()
    inventory = Inventory()

    filePath = driveFetcher.fetchLatestExcelFromFolder("Nhu Tin")
    inventory.ingestInventoryFromExcel(filePath)

if __name__ == "__main__":
    main()