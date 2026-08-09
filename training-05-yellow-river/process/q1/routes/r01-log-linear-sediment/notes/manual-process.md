# Question 1 Manual Process

## Objective

Record the manual reasoning process for question 1.

## Inputs

- Problem statement and attachments: source files in the project attachment folder.
- Working folder: `..`

## Manual Steps

1. Confirm the target quantities and required time scale.
2. Review raw attachment fields and identify usable variables.
3. Record cleaning decisions and abnormal-value handling.
4. Check model assumptions against the physical meaning of the data.
5. Compare final estimates with intermediate summaries for consistency.

## Outputs

- Method note: `question1-analysis.md`
- Code: `../code/analyze_question1.py`
- Processed data: `../data/processed/cleaned_hydro_timeseries.csv`
- Final result tables: `../results`
- Validation and diagnostics: `../qa`

## Validation

- Confirm units are consistent across source data, formulas, and outputs.
- Check that all reported result tables can be regenerated from the code.
- Record any manual overrides or excluded records here.

## Handoff Notes

- Status: initialized.
- Next action: update this file when the manual review of question 1 is completed.
