import pvlib
import pandas as pd
from datetime import datetime
import csv
import matplotlib.pyplot as plt
import math

LONGITUDE = 12.689624273207468
LATITUDE = 48.489533021697
ELEVATION = 500

PANEL_EFF = 20

#date = "19_01_2025"
#date = "20_01_2025"
#date = "6_02_2025"
#date = "1_02_2025"
date = "10_02_2025"
#date = "27_01_2025"

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
	Modulfield(1731, PANEL_EFF, 15, 250),		# West
	Modulfield(1381, PANEL_EFF, 15, 70),			# Ost
	Modulfield(66, PANEL_EFF, 15, 230),			# Hang links
	Modulfield(189, PANEL_EFF, 60, 250),			# Hang rechts
	Modulfield(219, PANEL_EFF, 15, 225),			# Sued West
	Modulfield(73, PANEL_EFF, 15, 45)			# Nord Ost
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
	df['Datetime'] = df['Datetime'].dt.tz_localize('Europe/Berlin')  # Lokale Zeit berücksichtigen
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
calc_power = []
calc_power_simple = []
calc_dni = []
calc_dhi = []
calc_dni_error = []
calc_dhi_error = []
calc_dni_clear = []
calc_gti = []
calc_gti_simple = []

loc = pvlib.location.Location(LATITUDE, LONGITUDE, 'Europe/Berlin', ELEVATION)
clearsky = loc.get_clearsky(dataMeasured.index)

linke_turbidity = pvlib.clearsky.lookup_linke_turbidity(dataMeasured.index, LATITUDE, LONGITUDE)

for index, row in dataMeasured.iterrows():
	date_time = index

	solarpos = pvlib.solarposition.get_solarposition(date_time, LATITUDE, LONGITUDE)
	solar_zenith = solarpos['zenith'].values[0]
	solar_azimuth = solarpos['azimuth'].values[0]
	solar_zenith_app = solarpos['apparent_zenith'].values[0]

	#dni_extra = 1361.0
	dni_extra = pvlib.irradiance.get_extra_radiation(date_time)

	dni_clear = clearsky['dni'][date_time]

	if dni_clear < 0.0:
		dni_clear = 0.0

	pressure = pvlib.atmosphere.alt2pres(ELEVATION)

	am_rel = pvlib.atmosphere.get_relative_airmass(solar_zenith, 'kastenyoung1989')
	am_abs = pvlib.atmosphere.get_absolute_airmass(am_rel, pressure)

	dni_clear2 = 0.0

	#clearsky2 = pvlib.clearsky.ineichen(solar_zenith_app, am_abs, linke_turbidity, ELEVATION, dni_extra)
	#dni_clear2 = clearsky2['dni'][date_time]

	#clearsky2 = pvlib.clearsky.simplified_solis(90 - solar_zenith, pressure = pressure, dni_extra = dni_extra)
	#dni_clear2 = clearsky['dni'][date_time]

	# Daneshyar–Paltridge–Proctor
	#dni_clear2 = 950.2 * (1.0 - math.exp(-0.075 * (90.0 - solar_zenith)))

	# Haurwitz
	#ghi_clear = 1098 * math.cos(solar_zenith * math.pi / 180) * math.exp(-0.057 / math.cos(solar_zenith * math.pi / 180))
	#irr_est2 = pvlib.irradiance.erbs_driesse(ghi_clear, solar_zenith, dni_extra, max_zenith = 87)
	#dni_clear2 = irr_est2['dni']

	# Meinel
	#if solar_zenith < 88:
	#	am_2 = 1.0 / math.cos(solar_zenith * math.pi / 180)
	#	am_factor = pow(am_2, 0.678)
	#	dni_clear2 = dni_extra * pow(0.7, am_factor)

	# Laue
	if solar_zenith < 90:
		am_2 = 1.0 / math.cos(solar_zenith * math.pi / 180)
		am_factor = pow(am_2, 0.678)
		dni_clear2 = dni_extra * ((1.0 - 0.14 * ELEVATION / 1000) * pow(0.7, am_factor) + 0.14 * ELEVATION / 1000)

	dni_clear2 = max(dni_clear2, 0)
	calc_dni_clear.append((date_time, dni_clear2))

	albedo = 0.0

	ghi = convert_string_to_float(row['Einstrahlung'])

	total_power = 0.0
	total_power_simple = 0.0

	mf_count = 0

	for mf in listModulfields:
		mf_count += 1

		irr_est = pvlib.irradiance.erbs_driesse(ghi, solar_zenith, dni_extra, max_zenith = 87)
		#irr_est = pvlib.irradiance.orgill_hollands(ghi, solar_zenith, date_time, max_zenith = 87)
		#irr_est = pvlib.irradiance.boland(ghi, solar_zenith, date_time, max_zenith = 87)
		#irr_est = pvlib.irradiance.louche(ghi, solar_zenith, date_time)

		dni_est = irr_est['dni']
		dhi = irr_est['dhi']

		#dni = dni_est
		dni = (ghi - dhi) * am_rel

		if True:
			if dni < 0:
				dni = 0
				dhi = ghi

			if solar_zenith > 87:
				dni = 0
				dhi = ghi
			elif solar_zenith > 80:
				max_dni = dni_clear2 * 1.1

				if dni > max_dni:
					calc_dni_error.append((date_time, dni))
					calc_dhi_error.append((date_time, dhi))

					dni = max_dni

					dir_hor = dni * math.cos(solar_zenith * math.pi / 180)
					dhi = ghi - dir_hor

		calc_dni.append((date_time, dni))
		calc_dhi.append((date_time, dhi))

		angle_of_incidence = pvlib.irradiance.aoi(mf.tilt, mf.direction, solar_zenith, solar_azimuth)

		incidence_angle_modifier = pvlib.iam.ashrae(angle_of_incidence)

		#print(str(date_time) + " GHI: " + str(ghi) + " DNI: " + str(dni) + " DHI: " + str(dhi))
		#print(str(date_time) + " SZ: " + str(solar_zenith) + " IA: " + str(angle_of_incidence) + " IAM: " + str(incidence_angle_modifier))
		#print(str(date_time) + " SZ: " + str(solar_zenith) + " DNI: " + str(dni) + " DHI: " + str(dhi) + " Erbs: " + str(dni_est) + " Clear: " + str(dni_clear))

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

		gti = mf_irr_dir + mf_irr_diff

		#print(str(date_time) + " SZ: " + str(solar_zenith) + " MFT: " + str(mf.tilt) + " GHI: " + str(ghi) + " GTI: " + str(mf_irr_tot))

		eff_corrected = mf.efficiency * 0.98

		mf_power = gti * mf.area * eff_corrected / 100.0
		total_power += mf_power

		if 90 > solar_zenith >= 0:
			solar_height = 90 - solar_zenith
			gti_simple = dni * (math.cos(solar_height * math.pi / 180) * math.sin(mf.tilt * math.pi / 180) * math.cos((mf.direction - solar_azimuth) * math.pi / 180) + math.sin(solar_height * math.pi / 180) * math.cos(mf.tilt * math.pi / 180))
			gti_simple = max(gti_simple, 0) + dhi
			mf_power_simple = gti_simple * mf.area * eff_corrected / 100.0
			total_power_simple += mf_power_simple

			if mf_count == 2:
				calc_gti.append((date_time, gti))
				calc_gti_simple.append((date_time, gti_simple))

				print(str(date_time) + " SZ: " + str(solar_zenith) + " SA: " + str(solar_azimuth) + " GHI: " + str(ghi) + " GTI: " + str(gti) + "GTI_S: " + str(gti_simple))

	#print(str(date_time) + " POWER: " + str(total_power))

	calc_power.append((date_time, total_power))
	calc_power_simple.append((date_time, total_power_simple))

#write_list_to_csv(dataCalculated, "data/calculated_" + date + ".csv")

# Plotten der Ergebnisse
values_power_measured = dataMeasured['Liefern'].apply(convert_string_to_float)
values_ghi = dataMeasured['Einstrahlung'].apply(convert_string_to_float)

figure, axis = plt.subplots(2, 1, figsize = (10, 5), tight_layout = True)

axis[0].plot(dataMeasured.index, values_power_measured, marker='', linestyle='-', color='blue', label='Power Measured')
axis[0].plot([row[0] for row in calc_power], [row[1] for row in calc_power], marker='', linestyle='--', color='green', label='Power Calculated')
axis[0].plot([row[0] for row in calc_power_simple], [row[1] for row in calc_power_simple], marker='', linestyle='--', color='cyan', label='Power Calculated Simple')

axis[1].plot(dataMeasured.index, values_ghi, marker='', linestyle='-', color='blue', label='GHI')
axis[1].plot([row[0] for row in calc_dni], [row[1] for row in calc_dni], marker='', linestyle='--', color='green', label='DNI')
axis[1].plot([row[0] for row in calc_dhi], [row[1] for row in calc_dhi], marker='', linestyle='--', color='cyan', label='DHI')
#axis[1].plot(clearsky.index, clearsky['dni'], marker='', linestyle='--', color='purple', label='DNI Clear')
#axis[1].plot([row[0] for row in calc_dni_clear], [row[1] for row in calc_dni_clear], marker='', linestyle='--', color='magenta', label='DNI Clear 2')
axis[1].plot([row[0] for row in calc_dni_error], [row[1] for row in calc_dni_error], marker='x', linestyle='', color='red', label='DNI Error')
axis[1].plot([row[0] for row in calc_dhi_error], [row[1] for row in calc_dhi_error], marker='x', linestyle='', color='orange', label='DHI Error')

axis[1].plot([row[0] for row in calc_gti], [row[1] for row in calc_gti], marker='', linestyle=':', color='purple', label='GTI')
axis[1].plot([row[0] for row in calc_gti_simple], [row[1] for row in calc_gti_simple], marker='', linestyle=':', color='magenta', label='GTI Simple')



axis[0].set_xlabel('Datetime')
axis[0].set_ylabel('Power [W]')
axis[0].set_title('Available Power')
axis[0].legend()
axis[0].grid(True)

axis[1].set_xlabel('Datetime')
axis[1].set_ylabel('Irradiance [W/m^2]')
axis[1].set_title('Irradiance')
axis[1].legend()
axis[1].grid(True)

plt.show()
