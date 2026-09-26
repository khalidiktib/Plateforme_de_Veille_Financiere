# tester juste la section connue, max 3 PDF
#from collectors.bam.bam_pipeline import run_bam_pipeline
#from collectors.bam.bam_collector import SEED_SECTIONS

#run_bam_pipeline(limite_par_section=3, sections=[SEED_SECTIONS[0]])


# Tester toutes les sections d'un coup

from collectors.bam.bam_pipeline import run_bam_pipeline

run_bam_pipeline(limite_par_section=2)  # 2 PDF max par section, les 18 sections
