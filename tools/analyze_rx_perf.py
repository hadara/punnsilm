import os
import csv
import sys
import glob
import json
import time
import pprint
import logging
import optparse

STATS_DIR = "/tmp"

stats_dir = STATS_DIR

STAT_FRESHNESS_THRESHOLD_SEC = 3600

SORT_FUNCS = {
    'evaluations': lambda x: x['evaluations'],
    'matches': lambda x: x['matches'],
    'total_time': lambda x: x['total_time'],
    'time_per_evaluation': lambda x: x['time_per_evaluation'],
}

def get_grouper_name_from_stat_file(stat_file):
    return stat_file.split("_", 2)[2].rsplit(".", 1)[0]

def get_statfiles():
    statfiles = glob.glob(os.path.join(stats_dir, "punnsilm_stats_*.json"))
    retl = []
    for stat_file in statfiles:
        if not os.path.isfile(stat_file):
            logging.warn('%s is not a file' % (stat_file,))
            continue
    
        file_age_sec = time.time() - os.path.getmtime(stat_file)
        if file_age_sec > STAT_FRESHNESS_THRESHOLD_SEC:
            logging.warn("skiping %s because it's too old (%ds)" % (stat_file, int(file_age_sec)))
            continue

        retl.append(stat_file)
    return retl

def flatten_stat_dict(grouper_name, stat_file):
    retl = []
    with open(stat_file, "r", encoding="utf-8") as fd:
        statd = json.loads(fd.read())
        for subgroup_name, subgroup in statd.items():
            for rx, perf_counters in subgroup.items():
                key = "%s:%s:%s" % (grouper_name, subgroup_name, rx)
                perf_counters['key'] = key
                retl.append(perf_counters)
    return retl

def calculate_additional_stats(statl):
    for v in statl:
        v['time_per_evaluation'] = v['total_time'] / v['evaluations']

# <outputs>
OUTPUT_FIELD_ORDER = ('key', 'evaluations', 'matches', 'total_time', 'time_per_evaluation')

def output_csv(statl):
    csv_writer = csv.DictWriter(sys.stdout, OUTPUT_FIELD_ORDER)
    csv_writer.writeheader()
    for row in statl:
        csv_writer.writerow(row)

def output_json(statl):
    print(json.dumps(statl))

def output_pprint(statl):
    pprint.pprint(statl)

OUTPUTS = {
    'JSON': output_json,
    'CSV': output_csv,
    'pprint': output_pprint,
}
# </outputs>"

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option('--sort-by', help="""sort by this field (evaluations, matches, total_time, time_per_evaluation) default: time_per_evaluation""", dest="sort_by", default="time_per_evaluation")
    parser.add_option('--sort-direction', help="""either ASC or DESC""", dest="sort_direction", default="DESC")
    parser.add_option('--output-format', help="""Either JSON, CSV or pprint (default)""", default="pprint", dest="output_format")
    (options, args) = parser.parse_args()

    if options.sort_by not in SORT_FUNCS:
        logging.warn('unknown sort function %s specified' % (options.sort_by,))
        sys.exit(-1)
    else:
        sort_func = SORT_FUNCS[options.sort_by]

    if options.sort_direction not in ('ASC', 'DESC'):
        logging.warn('unknown sort direction %s specified' % (options.sort_direction,))
        sys.exit(-1)

    if options.output_format not in OUTPUTS:
        logging.warn('unknown output format %s specified' % (options.output_format,))
        sys.exit(-1)
    output_func = OUTPUTS[options.output_format]

    files = get_statfiles()
    merged_stats = []
    for stat_file in files:
        grouper_name = get_grouper_name_from_stat_file(stat_file)
        flatl = flatten_stat_dict(grouper_name, stat_file)
        merged_stats += flatl

    calculate_additional_stats(merged_stats)
    merged_stats.sort(key=sort_func)
    if options.sort_direction == 'DESC':
        merged_stats.reverse()

    output_func(merged_stats)
