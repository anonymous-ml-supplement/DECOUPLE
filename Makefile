.PHONY: reproduce audit coverage reviewer-check full-inference figures clean env-check
reproduce:
	bash scripts/reproduce_all.sh

audit:
	python3 scripts/audit_source_tree.py
	python3 scripts/audit_release_manifest.py
	python3 scripts/check_anonymity.py
	python3 scripts/verify_hashes.py frozen
	python3 scripts/verify_hashes.py expected

coverage:
	python3 scripts/audit_tmlr_v5_coverage.py

reviewer-check:
	$(MAKE) audit
	$(MAKE) coverage
	$(MAKE) reproduce

figures:
	python3 scripts/rebuild_paper_figures.py reproduced/work

full-inference:
	bash scripts/reproduce_full_vef_bootstrap.sh
	bash scripts/reproduce_full_permutation.sh
	bash scripts/reproduce_full_zero_anchor.sh

clean:
	rm -rf reproduced/work reproduced/logs reproduced/paper reproduced/figures
	mkdir -p reproduced
	touch reproduced/.gitkeep

# Optional exact-match check for the successfully tested lab environment.
env-check:
	python3 scripts/check_environment.py --strict
