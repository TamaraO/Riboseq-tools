'''
# Author: Tamara Ouspenskaia
# Date: 01/14/2020
# Objective: This script calculates the sequencing coverage at variant sites
'''


# This script requires: <br>
# - a BAM file of aligned reads
# - the .annot file generated by the variant_to_protein.sh script
# - the analysis.tab file generated by the variant_analysis.sh script
#
#
# The output of this script is: <br>
# - Read coverage at the variant
# - Mean and median coverage at the variant +/- 20 region
# - Coverage and identity of the WT and the mutant alleles

import argparse
import pysam
from collections import Counter
import statistics
import pandas as pd
import numpy as np

parser = argparse.ArgumentParser()

#Inputs
parser.add_argument("--bam", required = True, help = "Path to BAM file with aligned reads")
parser.add_argument("--mut_annot", required = True, help = "Path to annot file generated by variant_to_protein script")
parser.add_argument("--analysis_tab", required = True, help = "Path to analysis.tab file genereated by variant_analysis script")

#Outputs
parser.add_argument("--read_counts", required = True, help = "Path to the output file of read counts per SNV")
parser.add_argument("--over3_all", required = True, help = "Path to output file with number of ORFs per type with at least 3 reads at SNV")
parser.add_argument("--over3_pass", required = True, help = "Path to output file with number of ORFs per type with at least 3 reads at SNVs that PASS filter")

args = parser.parse_args()

print("Starting the snv_coverage script")

#Load inputs:

bam = pysam.AlignmentFile(args.bam, "rb" )
annot = pd.read_csv(args.mut_annot, header=0, sep='\t')
analysis_tab = pd.read_csv(args.analysis_tab, header=0, sep='\t')
print("All inputs are loaded")

#Get read counts across the SNV locus

def variant_metrics(row):
    surround_cov = []
    all_pos_counts = []
    variant_nt = []
    for pileupcolumn in bam.pileup(str(row['mut_chr']), row['mut_location']-20, row['mut_location']+20, stepper='nofilter', truncate=True):
        surround_cov.append(pileupcolumn.n)
        if pileupcolumn.pos == row['mut_location']-1:
            row['variant_cov'] = pileupcolumn.n
            for pileupread in pileupcolumn.pileups:
                if not pileupread.is_del and not pileupread.is_refskip:
                    # query position is None if is_del or is_refskip is set.
                    variant_nt.append(pileupread.alignment.query_sequence[pileupread.query_position])
                    row['variant_nt_counts'] = dict(Counter(variant_nt))
        if pileupcolumn.pos != row['mut_location']-1:
            pass
            #index = pileupcolumn.n
            #counter = 0
            #nt = []
            #for pileupread in pileupcolumn.pileups:
                #if not pileupread.is_del and not pileupread.is_refskip:
                    # query position is None if is_del or is_refskip is set.
                    #counter += 1
                    #nt.append(pileupread.alignment.query_sequence[pileupread.query_position])
                    #nt_counts = dict(Counter(nt))
                    #if counter == index:
                        #all_pos_counts.append(nt_counts)
                    #else:
                        #continue
    if not surround_cov:
        row['median_surround_cov'] = 0
        row['mean_surround_cov'] = 0
    else:
        row['median_surround_cov'] = statistics.median(surround_cov)
        row['mean_surround_cov'] = statistics.mean(surround_cov)
    return(row)



# Extract the # of reads supporting wt vs. mut:

def count_reads(row):
    if isinstance(row['variant_nt_counts'], dict):
            if row['wt'] in row['variant_nt_counts']:
                row['wt_cov'] = row['variant_nt_counts'][row['wt']]
            else:
                row['wt_cov'] = 0
            if row['mut'] in row['variant_nt_counts']:
                row['mut_cov'] = row['variant_nt_counts'][row['mut']]
            else:
                row['mut_cov'] = 0
    else:
            row['wt_cov'] = 0
            row['mut_cov'] = 0
    return row



annot_out = annot.apply(variant_metrics, axis=1)
print('BAM file is processed')

annot_out_count = annot_out.apply(count_reads, axis=1)
print('Variant coverage is calculated')

count_subset = annot_out_count[['ORF_ID', 'mean_surround_cov', 'median_surround_cov',
       'mut', 'trans_strand', 'variant_ORF_id', 'variant_cov',
       'variant_id', 'variant_nt_counts', 'variant_qc',
       'wt', 'wt_cov', 'mut_cov']]

annot_keep = analysis_tab[['variant_ORF_id', 'ORF_type', 'header',
       'mut_len', 'mut_seq', 'wt_len', 'wt_seq']]

merged = annot_keep.merge(count_subset, on='variant_ORF_id', how='left')
merged = merged.drop_duplicates(subset='mut_seq')

merged[['ORF_ID', 'mean_surround_cov', 'median_surround_cov',
       'mut', 'trans_strand', 'variant_ORF_id', 'variant_cov',
       'variant_id', 'variant_nt_counts', 'variant_qc',
       'wt', 'wt_cov', 'mut_cov', 'ORF_type', 'header','mut_len', 'wt_len']].to_csv(args.read_counts, header=True, index=False, sep='\t')


# For SNVs supported by at least 3 reads, get the # of ORF_types. Do it for all and for PASS filter.

over3_snvs = merged[(merged['mut_cov'] > 3) &  (merged['mut_cov']/merged['mut_cov'] > 0.1)]

over3_snvs.groupby('ORF_type').count()['variant_ORF_id'].to_csv(args.over3_all, sep='\t', header=None, index=True)

over3_snvs_pass = over3_snvs[over3_snvs['variant_qc'] == 'PASS']

over3_snvs_pass.groupby('ORF_type').count()['variant_ORF_id'].to_csv(args.over3_pass, sep='\t', header=None, index=True)
