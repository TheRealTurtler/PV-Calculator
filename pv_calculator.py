import pvlib
import pandas as pd
from datetime import datetime
import csv
import matplotlib.pyplot as plt

LONGITUDE = 11.5188316
LATITUDE = 48.1554621

PANEL_EFF = 20

date = "19_01_2025"
#date = "20_01_2025"
#date = "6_02_2025"
#date = "1_02_2025"

#MODEL_IRRADIANCE = 'isotropic'
#MODEL_IRRADIANCE = 'klucher'
MODEL_IRRADIANCE = 'haydavies'
#MODEL_IRRADIANCE = 'reindl'
#MODEL_IRRADIANCE = 'king'
#MODEL_IRRADIANCE = 'perez'
#MODEL_IRRADIANCE = 'perez-driesse'

class Modulfield:
	def __init__(
			self,
			_area,
			_efficiency,
			_tilt,
			_direction
	):
		self.area = _area
		self.efficiency = _efficiency
		self.tilt = _tilt
		self.direction = _direction

listModulfields = [
	Modulfield(1731, PANEL_EFF, 20, 250),		# West
	Modulfield(1381, PANEL_EFF, 20, 70),			# Ost
	Modulfield(66, PANEL_EFF, 40, 180),			# Hang links
	Modulfield(189, PANEL_EFF, 40, 180),			# Hang rechts
	Modulfield(219, PANEL_EFF, 30, 225),			# Sued West
	Modulfield(73, PANEL_EFF, 30, 45)			# Nord Ost
]


def load_csv_for_date(date_str):
	# Datumsformat: TT_MM_JJJJ
	date_obj = datetime.strptime(date_str, "%d_%m_%Y")
	# Datei Name
	file_name = f"data/PD2106-0023_5mData_{date_str}.csv"

	# CSV-Datei laden
	df = pd.read_csv(file_name, sep=';')

	# Datumszeit Spalte kombinieren und zu DatetimeIndex machen
	df['Datetime'] = pd.to_datetime(df['Uhrzeit'], format='%H:%M').apply(
		lambda x: x.replace(year=date_obj.year, month=date_obj.month, day=date_obj.day))
	df.set_index('Datetime', inplace=True)

	# Umordnen und nicht benötigte Spalte entfernen
	df = df[['Liefern', 'Einstrahlung', 'Aussentemperatur']]

	return df


def write_list_to_csv(data_list, file_name):
	"""
	Schreibt eine Liste von Tupeln in eine CSV-Datei.

	:param data_list: Liste von Tupeln, z.B. [(datetime, total_power), ...]
	:param file_name: Name der CSV-Datei
	"""
	# CSV-Datei schreiben
	with open(file_name, 'w', newline='') as file:
		writer = csv.writer(file)
		# Header schreiben
		writer.writerow(['Datetime', 'Total_Power'])
		# Daten schreiben
		for row in data_list:
			writer.writerow(row)

def convert_string_to_float(string):
	# Ersetzen der Tausendertrennzeichen und Dezimalzeichen
	string = string.replace('.', '').replace(',', '.')
	# Konvertieren zu float
	result = float(string)
	return result

dataMeasured = load_csv_for_date(date)
dataCalculated = []

for index, row in dataMeasured.iterrows():
	date_time = index

	solarpos = pvlib.solarposition.get_solarposition(date_time, LATITUDE, LONGITUDE)
	solar_zenith = solarpos['zenith'].values[0] - 5
	solar_azimuth = solarpos['azimuth'].values[0]

	dni_extra = 1361.0
	#dni_extra = pvlib.irradiance.get_extra_radiation(date_time)

	albedo = 0.0

	ghi = convert_string_to_float(row['Einstrahlung'])

	total_power = 0.0

	for mf in listModulfields:
		erbsout = pvlib.irradiance.erbs_driesse(ghi, solar_zenith, dni_extra)

		dni = erbsout['dni']
		dhi = erbsout['dhi']

		angle_of_incidence = pvlib.irradiance.aoi(mf.tilt, mf.direction, solar_zenith, solar_azimuth)

		incidence_angle_modifier = pvlib.iam.ashrae(angle_of_incidence)

		#print(str(date_time) + " GHI: " + str(ghi) + " DNI: " + str(dni) + " DHI: " + str(dhi))
		print(str(date_time) + " SZ: " + str(solar_zenith) + " IA: " + str(angle_of_incidence) + " IAM: " + str(incidence_angle_modifier))

		irrads = pvlib.irradiance.get_total_irradiance(
			mf.tilt, mf.direction,
			solar_zenith, solar_azimuth,
			dni, ghi, dhi, dni_extra,
			albedo = albedo,
			model = MODEL_IRRADIANCE
		)

		mf_irr_dir = irrads['poa_direct']
		mf_irr_diff = irrads['poa_diffuse']

		mf_irr_dir *= incidence_angle_modifier

		mf_irr_tot = mf_irr_dir + mf_irr_diff

		eff_corrected = mf.efficiency * 0.90

		mf_power = mf_irr_tot * mf.area * eff_corrected / 100.0
		total_power += mf_power

	#print(str(date_time) + " POWER: " + str(total_power))

	dataCalculated.append((date_time, total_power))

#write_list_to_csv(dataCalculated, "data/calculated_" + date + ".csv")

# Plotten der Ergebnisse
dates = [row[0] for row in dataCalculated]
values_power_calc = [row[1] for row in dataCalculated]
values_power_measured = dataMeasured['Liefern'].apply(convert_string_to_float)

figure, axis = plt.subplots(1, 1, figsize = (10, 5), tight_layout = True)

axis.plot(dates, values_power_calc, marker='o', linestyle='-', color='b', label='Power Calculated')
axis.plot(dataMeasured.index, values_power_measured, marker='x', linestyle='--', color='r', label='Power Measured')

axis.set_xlabel('Datetime')
axis.set_ylabel('Power [W]')
axis.set_title('Available Power')
axis.legend()
axis.grid(True)

plt.show()
