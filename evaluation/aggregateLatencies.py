import csv

CHURN_RATES = [0.01, 0.02, 0.05, 0.1, 0.2]
OUTPUT_FILENAME = 'latencyLogAggregated.csv'

if __name__ == '__main__':
    csv_data = {}
    for churn_rate, csv_filename in [(churn_rate, f"latencyLogOutputCR{churn_rate}.csv") for churn_rate in CHURN_RATES]:
        print(f"Reading {csv_filename}...")
        with open(csv_filename, newline='') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            for seconds, transactions in csv_reader:
                seconds_data = csv_data.get(int(seconds), {})
                seconds_data[churn_rate] = int(transactions)
                csv_data[int(seconds)] = seconds_data
    
    min_latency = min(csv_data.keys())
    max_latency = max(csv_data.keys())

    print(f"Writing {OUTPUT_FILENAME}...")
    with open(OUTPUT_FILENAME, 'w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=',')
        csv_writer.writerow(["seconds"] + CHURN_RATES)
        for seconds in range(min_latency, max_latency+1):
            csv_writer.writerow([seconds] + [csv_data.get(seconds, {}).get(churn_rate, 0) for churn_rate in CHURN_RATES])