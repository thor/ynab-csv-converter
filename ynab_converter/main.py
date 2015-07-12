
def parse_opts():
	import docopt
	usage = """ynab-converter
Converts transactionlists from a format to ynab format

Usage: ynab-converter [options] FORMULA INFILE...

Options:
	-h, --help  show this help

Supported formats:
  nordnet      "XLS compatible" (read: csv) export from nordnet.dk
  sparekassen  Sparekassen Kronjylland netbank export
  danskebank   CSV tab-separated export from Danske Bank netbank
"""
	return docopt.docopt(usage)


def main():
	from . import load_formula
	import formats.ynab
	import os.path
	import shutil
	import importlib
	from itertools import chain
	opts = parse_opts()
	formula = load_formula(opts['FORMULA'])

	inform_modname = 'ynab_converter.formats.' + formula['format']
	informat = importlib.import_module(inform_modname)

	out_basename = os.path.join(formula['outpath'], formula['outprefix'])
	archive_basename = os.path.join(formula['archivepath'], formula['outprefix'])

	for import_file in opts['INFILE']:
		# Get the lines to import
		# (and cache the list, we will iterate through it multiple times)
		all_lines = list(informat.getlines(import_file))

		# Find the daterange we are importing
		import_min = min([line.date for line in all_lines])
		import_max = max([line.date for line in all_lines])

		# Find previously converted files
		previously_converted = list(find_daterange(out_basename, import_min, import_max))

		# Get all lines from those previously converted files
		prev_lines = chain(*(formats.ynab.getlines(path) for path in previously_converted))

		# Filter previous lines to only contain transactions inside the import daterange
		# (also cache this one, we do multiple lookups)
		consolidation_lines = list([line for line in prev_lines if import_min <= line.date <= import_max])

		# Filter import lines using the previously converted transactions
		unique_lines = [line for line in all_lines if line not in consolidation_lines]

		factor = formula.get('factor', 1)
		if factor != 1:
			# Multiply unique import lines by "factor"
			unique_lines = list([factor_line(line, formula['factor']) for line in unique_lines])

		if len(unique_lines) > 0:
			# Find the daterange we are exporting and create the name for the output file with that
			# We reverse the date order so that the files are sorted by newest transaction
			export_min = min([line.date for line in unique_lines])
			export_max = max([line.date for line in unique_lines])
			date_suffix = '-' + export_max.strftime('%Y%m%d') + '-' + export_min.strftime('%Y%m%d')
			output_filepath = out_basename + date_suffix + '.csv'

			# Write import lines to outputfile
			if os.path.exists(output_filepath):
				raise Exception("The file {path} already exists".format(path=output_filepath))
			formats.ynab.putlines(output_filepath, unique_lines)

			print("Wrote {written} out of {read} transactions to {path}"
			      .format(written=len(unique_lines),
			              read=len(all_lines),
			              path=output_filepath))
		else:
			print("No unique lines found in {path}".format(path=import_file))

		# Archive original file (use the total daterange for the filename)
		date_suffix = '-' + import_max.strftime('%Y%m%d') + '-' + import_min.strftime('%Y%m%d')
		archive_filepath = archive_basename + date_suffix + '.csv'
		if os.path.exists(archive_filepath):
			raise Exception("The file {path} already exists".format(path=archive_filepath))
		shutil.move(import_file, archive_filepath)


def factor_line(line, factor):
	from formats.ynab import YnabLine
	return YnabLine(line.date, line.payee, line.category, line.memo, factor * line.outflow, factor * line.inflow)


def find_daterange(basename, min_date, max_date):
	import datetime
	import re
	import glob
	file_pattern = re.compile(
		'^' + re.escape(basename) +
		'-(?P<to>\d{4}\d{2}\d{2})-(?P<from>\d{4}\d{2}\d{2}).csv')
	for path in glob.glob(basename + '*'):
		result = file_pattern.match(path)
		if result is None:
			raise Exception('Found file that does not match pattern: ' + path)
		fromdate = datetime.datetime.strptime(result.group('from'), '%Y%m%d')
		todate = datetime.datetime.strptime(result.group('to'), '%Y%m%d')
		if fromdate <= max_date or todate >= min_date:
			yield path
