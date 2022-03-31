import csv

CHURN_RATES = [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3]
OUTPUT_FILENAME = 'throughputLogAggregated.csv'

if __name__ == '__main__':
    csv_data = {}
    for churn_rate, csv_filename in [(churn_rate, f"throughputLogOutputCR{churn_rate}.csv") for churn_rate in CHURN_RATES]:
        print(f"Reading {csv_filename}...")
        with open(csv_filename, newline='') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            for row in csv_reader:
                if row['experiment'] == "total":
                    csv_data[churn_rate] = float(row['confirmed']) / float(row['submitted'])

    print(f"Writing {OUTPUT_FILENAME}...")
    with open(OUTPUT_FILENAME, 'w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=',')
        csv_writer.writerow(["churn rate", "throughput"])
        for churn_rate, throughput in csv_data.items():
            csv_writer.writerow([churn_rate, throughput])