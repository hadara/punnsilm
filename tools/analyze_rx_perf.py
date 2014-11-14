import os
import glob
import json
import time
import pprint
import logging
import optparse

STATS_DIR = "/tmp"

stats_dir = STATS_DIR

STAT_FRESHNESS_THRESHOLD_SEC = 3600

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
    retd = {}
    with open(stat_file, "r", encoding="utf-8") as fd:
        statd = json.loads(fd.read())
        for subgroup_name, subgroup in statd.items():
            for rx, perf_counters in subgroup.items():
                key = "%s:%s:%s" % (grouper_name, subgroup_name, rx)
                retd[key] = perf_counters
    return retd

def calculate_additional_stats(statl):
    for v in statl:
        v['time_per_evaluation'] = v['total_time'] / v['evaluations']
        
if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option('--sort-by', help="""sort by this field (evaluations, matches, total_time, time_per_evaluation)""", dest="sort_by")
    parser.add_option('--sort-direction', help="""either ASC or DESC""", dest="sort_direction")
    parser.add_option('--output-format', help="""Either JSON, CSV or print (default)""", default="print", dest="output_format")
    (options, args) = parser.parse_args()

    if options.sort_by:
        pass

    files = get_statfiles()
    merged_stats = []
    for stat_file in files:
        grouper_name = get_grouper_name_from_stat_file(stat_file)
        flatl = flatten_stat_dict(grouper_name, stat_file)
        merged_stats += flatl

    calculate_additional_stats(merged_stats)

    pprint.pprint(merged_stats)
