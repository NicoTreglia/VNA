#from easygui import *
import datetime
import csv
import getpass
import itertools
import requests
import os
import shutil
import time
import dicom
from PIL import Image, ImageFilter, ImagePalette
from dicom.examples import anonymize
import sys
from PyQt5 import QtCore, QtGui, QtWidgets
import view
options = {}
study_dict = {}
search_type = {}
study_search_terms = {}

class VNAGUI(QtWidgets.QMainWindow, view.Ui_MainWindow):

	def __init__(self):
		super(self.__class__, self).__init__()
		self.setupUi(self)
		################Assigning Button functionallity################
		self.login_btn.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(1))
		self.pass_box.returnPressed.connect(self.login_btn.click)
		self.mrn_box.returnPressed.connect(self.mrn_enter_btn.click)
		self.acc_box.returnPressed.connect(self.acc_enter_btn.click)
		self.mrn_btn.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(2))
		self.accnum_btn.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(2))
		self.keyword_btn.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(2))
		self.csv_btn.clicked.connect(self.csv_file)
		self.maninput_btn.clicked.connect(self.selected_type)
		self.mrn_enter_btn.clicked.connect(self.browse_folder)
		self.acc_enter_btn.clicked.connect(self.browse_folder)
		self.key_enter_btn.clicked.connect(self.browse_folder)
		self.png_btn.clicked.connect(self.getInputs)
		self.jpg_btn.clicked.connect(self.getInputs)
		self.dicom_btn.clicked.connect(self.getInputs)
		#self.video_btn.clicked.connect(self.getInputs)
		self.ok_btn.clicked.connect(lambda: self.retrieve_studies(self.user_box.text(),self.pass_box.text(), study_dict))
		self.view_btn.clicked.connect(lambda: self.close())
		self.cancel_btn.clicked.connect(lambda: self.close())
		#self.clear_btn.clicked.connect(self.removeSelected)

		# self.pushButton.clicked.connect(QtWidgets.QFileDialog.getExistingDirectory(self.savedir)) 
    ##########################################################################################################################################################################################################################################
	def selected_type(self):
		################Manual Input Type Selector################
		choice = 2
		if self.mrn_btn.isChecked(): choice = 3
		elif self.accnum_btn.isChecked(): choice = 4
		elif self.keyword_btn.isChecked(): choice = 5
		self.stackedWidget.setCurrentIndex(choice)
	##########################################################################################################################################################################################################################################
	def csv_file(self):
		################Handler for CSV File Input################
		csvfile  = QtWidgets.QFileDialog.getOpenFileName(self,"Select a File")
		fileList = list(csvfile)
		file 	 = fileList[0]
		print(file)
		with open(file,'r') as csvfile:
			read = csv.reader(csvfile, delimiter=',')
			for row in read:
				csvlist = row
		options['csv_file'] = csvlist
		self.browse_folder()
    ##########################################################################################################################################################################################################################################
	def browse_folder(self):
		################Handler for where to save images################
		savedir = QtWidgets.QFileDialog.getExistingDirectory(self,"Pick a folder")
		options['save_dir'] = savedir.replace("/","\\")
		self.stackedWidget.setCurrentIndex(6)
		
	##########################################################################################################################################################################################################################################
	def collect_studies(self, user, pw, query_terms):
		#####################################################################################################################
		################Collect all studies for a query################
		################Keyword arguments:################
		################acc_nums -- a list of accession numbers as strings################
		################user -- username (optional)################
		################pw -- password (optional)################
		################query_terms -- list of query terms, formatted as strings################
		################options -- dict with search parameters; the keys ['search_type', '', ''] are mandatory################
		######################################################################################################################
		series_search_terms = {}
		instance_search_terms = {}
		if options['start_date'] is not '':
			if options['end_date'] is not '':
				study_search_terms["StudyDate"] = options['start_date'] + "-" + options['end_date']
			else:
				study_search_terms["StudyDate"] = options['start_date'] + "-" + datetime.date.today().strftime("%Y%m%d")
		elif options['end_date'] is not '':
			study_search_terms["StudyDate"] = "19000101-" + options['end_date']

		if options['modality'] is not '':
			study_search_terms["ModalitiesInStudy"] = "*" + options['modality'] + "*"
			series_search_terms["Modality"] = options['modality']

		if "limit" in options and options["limit"] is not None:
			study_search_terms["limit"] = options["limit"]

		#####################################################################################################################
		if options['search_type'] == "accnum":
			for acc_num in query_terms:
				study_search_terms["AccessionNumber"] = acc_num

				r, url = self._search_vna(user, pw, search_terms=study_search_terms)
				if r.status_code == 204:
					print('Accession number', acc_num, 'has no studies associated with it.')
					continue
				
				study_id = r.json()[0]['0020000D']['Value'][0]
				study_info = (r.json()[0]['00081030']['Value'][0], r.json()[0]['00080020']['Value'][0])

				instance_dict = self._create_instance_dict(user, pw, study_id, series_search_terms, instance_search_terms)
				study_dict[acc_num] = (study_id, instance_dict, study_info)
		#####################################################################################################################
		elif options['search_type'] == "mrn":
			for mrn in query_terms:
				study_search_terms["PatientId"] = mrn
				r, url = self._search_vna(user, pw, search_terms=study_search_terms)
				if r.status_code == 204:
					print('MRN', mrn, 'has no studies associated with it.')
					continue	
				options['mrnfile']     = r.json()[0]['00080020']['Value'][0]
				#options['accfile'] 	   = r.json()[0]['00800061']['Value'][0]
				print (r.text)
				accnums_studyids_descr = [(json_data['00080050']['Value'][0], json_data['0020000D']['Value'][0],
					(json_data['00081030']['Value'][0], json_data['00080020']['Value'][0])) for json_data in r.json()]
				
				study_dict[mrn] = {}
				for acc_num, study_id, study_info in accnums_studyids_descr:
					instance_dict = self._create_instance_dict(user, pw, study_id, series_search_terms, instance_search_terms)
					study_dict[mrn][acc_num] = (study_id, instance_dict, study_info)
		#####################################################################################################################
		elif options['search_type'] == 'keyword':
			for keywords in itertools.permutations(query_terms):
				study_search_terms["StudyDescription"] = '*' + '*'.join(keywords) + '*'
				
				r, url = self._search_vna(user, pw, search_terms=study_search_terms)
				if r.status_code == 204:
					continue

				accnums_studyids_descr = [(json_data['00080050']['Value'][0], json_data['0020000D']['Value'][0],
					(json_data['00081030']['Value'][0], json_data['00080020']['Value'][0])) for json_data in r.json()]

				for acc_num, study_id, study_info in accnums_studyids_descr:
					instance_dict = self._create_instance_dict(user, pw, study_id, series_search_terms, instance_search_terms)
					study_dict[acc_num] = (study_id, instance_dict, study_info)
		#####################################################################################################################
		else:
			raise ValueError(options['search_type'])

		self.review_studies(study_dict)
		self.stackedWidget.setCurrentIndex(8)
	##########################################################################################################################################################################################################################################
	def _create_instance_dict(self, user, pw, study_id, series_search_terms, instance_search_terms):
		################Creates a File Directory for the incoming images################
		r, url = self._search_vna(user, pw, study_id=study_id, search_terms=series_search_terms)
		try:
			self.study_info = r.json()
		except Exception as e:
			raise ValueError('Search for study_id ' + study_id + ' encountered an error: ' + e)

		series = set([series_id['0020000E']['Value'][0] for series_id in self.study_info])

		instance_dict = {}
		for series_id in series:
			r, url = self._search_vna(user, pw, study_id=study_id, series=series_id, search_terms=instance_search_terms)

			series_info = r.json()
			instance_dict[series_id] = [instance_id['00080018']['Value'][0] for instance_id in series_info]

		return instance_dict
	##########################################################################################################################################################################################################################################
	def _search_vna(self, user, pw, study_id=None, series=None, region='prod', args=None, search_terms=None):
		################Use AcuoREST API to search VNA for study_id, series, and/or instance numbers associated with an accession number################
		################Makes Initial contact with VNA and Verifies Acess################
		if region == 'test':
			host = 'vnatest1vt'
			port = '8083'
		elif region == 'prod':
			host = '10.47.11.220'
			port = '8083'
		else:
			raise ValueError("Unsupported region")

		url = ''.join(['http://', host, ':', port, "/AcuoREST/dicomrs/search/studies"])

		if study_id is not None:
			url += "/" + study_id + "/series"

			if series is not None:
				url += "/" + series + "/instances"

		if len(search_terms) > 0:
			query_str = '?' + '&'.join([term + '=' + search_terms[term] for term in search_terms])
			url += query_str

		r = requests.get(url, auth=(user, pw))
		print(r.text)
		if r.status_code == 403:
			raise ValueError('Access denied. Probably incorrect login information.')
		elif r.status_code >= 500:
			print(url)
			raise ValueError('Server exception. Make sure arguments were specified in the right format.')
			
		return r, url
	##########################################################################################################################################################################################################################################
	def review_studies(self, study_dict):
		################################################################################
		################Allows the user to select among queried studies################
		################Displays all files at a STUDY level################
		################Each study will show how many SERIES it includes################
		################################################################################
		self.stackedWidget.setCurrentIndex(8)
		msg = "The following studies were found based on your query. Select which studies you want to download."
		title = 'Select studies to download'
		#####################################################################################################################
		if self.accnum_btn.isChecked():
			choices = []
			for acc_num in study_dict:
				_, instance_dict, study_info  = study_dict[acc_num]
				study_description, study_date = study_info
				choices.append("%s / %s (%d series) | %s" % (acc_num, study_description, len(instance_dict), self.reformat_date(study_date)))
			for choice in choices:
				self.study_box.addItem(choice)
		#####################################################################################################################	
		elif self.mrn_btn.isChecked():
			
			choices = []
			for mrn in study_dict:
				for acc_num in study_dict[mrn]:
					_, instance_dict, study_info  = study_dict[mrn][acc_num]
					study_description, study_date = study_info
					choices.append("%s | %s / %s (%d series) | %s" % (mrn, acc_num, study_description, len(instance_dict), self.reformat_date(study_date)))
					
			for choice in choices:
				self.study_box.addItem(choice)
	##########################################################################################################################################################################################################################################
	def reformat_date(self, date, in_format="%Y%m%d", out_format="%x"):
		return datetime.datetime.strptime(date, in_format).strftime(out_format)
	##########################################################################################################################################################################################################################################
	def retrieve_studies(self, user, pw, study_dict, metadata_only=False, get_series_name=None):
		#######################################################################################################################################################
		################Download all studies associated with an accession number################
		################Each accession number (study_id) is saved to a separate folder named with its study_id UID.################
		################Within that folder, each series is saved to a separate subfolder, named with the series description.################
		################Keyword arguments:################
		################user -- username################
		################pw -- password################
		################studies -- a list of tuples; each tuple study_id/series/instance################
		################options -- dict of parameters for how to retrieve the studies; must have 'save_dir', 'search_type' and 'overwrite' keys################
		################metadata_only -- if True, only retrieves image metadata xmls################
		################get_series_name -- specify a custom method for naming series subfolders (optional)################
		#######################################################################################################################################################
		################Names the indiv. studies################
		self.stackedWidget.setCurrentIndex(9)
		selection = []
		items = self.study_box.selectedItems() 
		for x in list(items):
			selection.append(str(x.text()))
		DL_Section = 100/len(selection)
		DL_Completed = DL_Section
		if self.accnum_btn.isChecked() or self.keyword_btn.isChecked():
			if selection is None:
				return None
			else:
				selected_accnums = [x[:x.find(' ')] for x in selection if x != "Add more choices"]
				study_dict 		 = {acc_num: study_dict[acc_num] for acc_num in selected_accnums}

		elif self.mrn_btn.isChecked():		

			if selection is None:
				return None
			else:
				selected_mrn_accnums = [x[:x.find('/')-1].split('|') for x in selection if x != "Add more choices"]
				selected_mrns 		 = set([x[0].strip() for x in selected_mrn_accnums])
				selected_accnums 	 = set([x[1].strip() for x in selected_mrn_accnums])
				study_dict 			 = {mrn: study_dict[mrn] for mrn in selected_mrns}
				for mrn in study_dict:
					study_dict[mrn]  = {acc_num: study_dict[mrn][acc_num] for acc_num in selected_accnums if acc_num in study_dict[mrn]}

		if get_series_name is None:
			def get_series_name(metadata_txt):
				txt = metadata_txt
				search = '<DicomAttribute tag="0008103E" vr="LO" keyword="SeriesDescription">\r\n      <Value number="1">'
				index = txt.find(search) + len(search)
				series_name = txt[index:index + txt[index:].find("</Value>")].lower()
				series_name = series_name.replace("/", "-")
				series_name = series_name.replace("\\", "-")
				series_name = series_name.replace(":", "-")
				series_name = series_name.replace("?", "")
				series_name = series_name.replace("*", "")

				search = '<DicomAttribute tag="00200011" vr="IS" keyword="SeriesNumber">\r\n      <Value number="1">'
				index = txt.find(search) + len(search)
				series_num = txt[index:index + txt[index:].find("</Value>")]
				series_name += "_" + series_num

				return series_name

		tot_time = time.time()
		#####################################################################################################################
		if self.accnum_btn.isChecked():
			for acc_num in study_dict:
				
				print("= Loading accession number", acc_num)
				accCount = 0
				study_id, instance_dict, _ = study_dict[acc_num]
				try:
					self.progressBar.setValue(DL_Completed)
					DL_Completed = DL_Completed + DL_Section
					print("= Loading accession number", acc_num)
					################Getting Studying from Accession Number################
					self.retrieve_study_from_id(user, pw, study_id, instance_dict, os.path.join(options['save_dir'], (acc_num)), metadata_only, get_series_name)
					accCount +=1
				except:
					raise ValueError("bad accession number "+str(acc_num))
		#####################################################################################################################	
		elif self.mrn_btn.isChecked():
			for mrn in study_dict:
				print("=== Loading MRN", mrn)
				accCount = 0
				for acc_num in study_dict[mrn]:
					self.progressBar.setValue(DL_Completed)
					DL_Completed = DL_Completed + DL_Section
					print("= Loading accession number", acc_num)
					study_id, instance_dict, _ = study_dict[mrn][acc_num]
					################Getting Studying From Each Accession Number inside each MRN################
					self.retrieve_study_from_id(user, pw, study_id, instance_dict, os.path.join(options['save_dir'], options['mrnfile'], ("Study #" + str(accCount))), metadata_only, get_series_name)
					accCount +=1
		#####################################################################################################################

		print("Time elapsed: %.1fs" % (time.time()-tot_time))
	##########################################################################################################################################################################################################################################
	def retrieve_study_from_id(self, user, pw, study_id, instance_dict, save_dir, metadata_only, get_series_name):
			if os.path.exists(save_dir):
				if self.overwrite_yes_btn.isChecked(): 
					print(save_dir, "may already have been downloaded (folder already exists in target directory). Skipping.")
					return
				else:
					shutil.rmtree(save_dir)
					while os.path.exists(save_dir):
						sleep(100)
						
			total = 0
			skip_ser = 0
			skip_inst = 0
			rmdir = []

			################Looping through each series in the study################
			for series_id in instance_dict:
				#Make a folder for it
				series_dir = save_dir + "\\" + series_id
				if not os.path.exists(series_dir):
					os.makedirs(series_dir)
				################Getting MetaData################
				r, url = self._retrieve_vna(user, pw, filepath = series_dir+"\\metadata.xml", study_id=study_id, series=series_id, metadata=True)
				if r is None:
					skip_ser += 1
					if options["verbose"]:
						print("Skipping series %s (no instances found)." % series_id)
					continue
				mdsearch = r.text
				search = '<DicomAttribute tag="00080060" vr="CS" keyword="Modality">\r\n      <Value number="1">'
				index = mdsearch.find(search) + len(search)
				md = mdsearch[index:index + mdsearch[index:].find("</Value>")]	
				options['md']=md
				################Rename the folder based on the metadata#################
				series_name = get_series_name(r.text)
				while os.path.exists(save_dir + "\\" + series_name):
					series_name += "+"

				try:
					os.rename(series_dir, save_dir + "\\" + series_name)
				except:
					series_name = "UnknownProtocol"
					while os.path.exists(save_dir + "\\" + series_name):
						series_name += "+"
					os.rename(series_dir, save_dir + "\\" + series_name)
				series_dir = save_dir + "\\" + series_name


				################Determine whether the series should be excluded based on the metadata################
				skip = False
				try:
					for exc_keyword in options['exclude_terms']:
						if exc_keyword in series_name:
							skip_ser += 1
							if options["verbose"]:
								print("Skipping series", series_name)
							rmdir.append(series_name)
							skip = True
							break
				except:
					pass

				if skip or metadata_only:
					continue


				################Load the actual images################
				if options["verbose"]:
					print("Loading series:", series_name)

				################Defines the file type for the retrieve call################

				imageString = ''
				if self.jpg_btn.isChecked(): imageString = 'jpeg'
				if self.png_btn.isChecked(): imageString = 'png'
				if self.dicom_btn.isChecked(): imageString = 'dcm'
				if self.video_btn.isChecked(): imageString = 'mpeg'


				################Loops through and retrieves all images in the series################
				for count, instance_id in enumerate(instance_dict[series_id]):
					r, _ = self._retrieve_vna(user, pw, filepath=series_dir+"\\"+str(count)+"."+imageString, study_id=study_id, series=series_id, instance=instance_id, anonymize_dcm=(not options["keep_phi"]))
					

					if r is not None:
						skip_inst += 1

				total += count

			if len(rmdir)>0 and not os.path.exists(save_dir+"\\others"):
				os.makedirs(save_dir+"\\others")

				for d in rmdir:
					os.rename(save_dir + "\\" + d, save_dir + "\\others\\" + d)
				################Removes Metadata################
			#print(series_dir)
			# tempdir=os.path.join(series_dir,"..")
			# parentdir=os.path.abspath(tempdir)
			# folderlist=os.listdir(parentdir)
			# for folder in folderlist:
			# 	print("folder:     ",folder)
			# 	tempdir2=parentdir+"\\"+folder
			# 	filelist=os.listdir(tempdir2)
			# 	for file in filelist:
			# 		if file.endswith(".xml"):
			# 			os.remove(os.path.join(tempdir2,file))
	##########################################################################################################################################################################################################################################
	def _retrieve_vna(self, user, pw, filepath, study_id=None, series=None, instance=None, region='prod', metadata=False, anonymize_dcm=True):
			################################################################################################################
			################Retrieve dicom files and metadata associated with a study_id/series/instance################
			################If metadata is true, filepath should end in xml. Else end in dcm or jpeg or png.################
			################################################################################################################
			################Determines image type to build query string################
			if filepath[-4:] == 'jpeg':
				imageType = 'image/jpeg'
			elif filepath[-4:] == 'mpeg':
				imageType = 'video/mp4'
			elif filepath[-3:] == 'png':
				imageType = 'image/png'
			elif filepath[-3:] == 'dcm':
				imageType = 'application/dicom'

			################Determines The Environment################
			if region == 'test':
				host = 'vnatest1vt'
				port = '8083'
			elif region == 'prod':
				host = '10.47.11.220'
				port = '8083'
			else:
				raise ValueError("Unsupported region")
		#####################################################################################################################
			if metadata:
				url = ''.join(['http://', host, ':', port,"/AcuoREST/dicomrs/retrieve/studies/",
								study_id])

				if series is not None:
					url += "/series/" + series
					if instance is not None:
						url += "/instance_dict/" + instance

				url += "/metadata"+"?contentType=application/xml"

				r = requests.get(url, auth=(user, pw))

				if r.status_code != 200:
					return None, url

				with open(filepath, 'wb') as fd:
					for chunk in r.iter_content(chunk_size=128):
						fd.write(chunk)
		#####################################################################################################################
			else:
				url = ''.join(['http://', host, ':', port,
					"/AcuoREST/wadoget?requestType=WADO&contentType=", imageType ,"&studyUID=",study_id])

				if series is not None:
					url += "&seriesUID=" + series
					if instance is not None:
						url += "&objectUID=" + instance

				r = requests.get(url, auth=(user, pw)) 

				if r.status_code != 200:
					return None, url



				################Anonymization of DICOM images if Needed################
				if anonymize_dcm and imageType == 'application/dicom':
					save_dir = os.path.dirname(filepath)
					with open(save_dir + "\\temp.dcm", 'wb') as fd:
						for chunk in r.iter_content(chunk_size=128):
							fd.write(chunk)

					try:
						anonymize.anonymize(filename = save_dir + "\\temp.dcm", output_filename=filepath)
						os.remove(save_dir + "\\temp.dcm")

					except:
						print("Anonymization failed!")
						os.rename(save_dir + "\\temp.dcm", filepath)

				################Takes JPEG or PNG Files and Blurs PHI################
				else:
					with open(filepath, 'wb') as fd:
						for chunk in r.iter_content(chunk_size=128):
							fd.write(chunk)		
					################Blurs Based Ultrasounds and Echos from Modality field################	
					if(options['md'] == 'US'):
						try:
							################Blurs larger Images################
							image 		  = Image.open(filepath)
							if image.mode == "P": image = image.convert('P', palette=Image.ADAPTIVE, colors=10).convert("RGB")
							cropped_image = image.crop((1,1,1000,80))
							try:
								################Blurs larger Images################
								blurred_image = cropped_image.filter(ImageFilter.GaussianBlur(radius=5))
								image.paste(blurred_image,(1,1,1000,80))
								image.save(filepath)
								image.close()
							except:
								################Blurs smaller Images################
								cropped_image = image.crop((1,1,800,60))
								blurred_image = cropped_image.filter(ImageFilter.GaussianBlur(5))
								image.paste(blurred_image,(1,1,800,60))
								image.save(filepath)
								image.close()
						except:
							print('failed: ' + image.mode)

			return r, url
	##########################################################################################################################################################################################################################################
	def getInputs(self):
		if self.png_btn.isChecked() or self.jpg_btn.isChecked() or self.dicom_btn.isChecked() or self.video_btn.isChecked():
			user = self.user_box.text()
			pw   = self.pass_box.text()
			print(user)
			################Define Search Type################
			if self.mrn_btn.isChecked():
				options['search_type'] = "mrn"
				options['review']      = True
				if self.maninput_btn.isChecked():
					query_terms 			 = (self.mrn_box.text()).replace(',', ' ').split()
					options['start_date'] 	 = self.mrn_start_date_box.text()
					options['end_date']		 = self.mrn_end_date_box.text()
					#options['DOB']			 = self.mrn_dob_box.text()
					options['modality']		 = self.mrn_modality_box.text()
					options['exclude_terms'] = (self.mrn_keyword_box.text()).replace(',', ' ').split()
					options['verbose'] 		 = True
					options['keep_phi'] 	 = False

			elif self.accnum_btn.isChecked():
				options['search_type'] = "accnum"
				options['review']      = False
				if self.maninput_btn.isChecked():
					query_terms 			 = (self.acc_box.text()).replace(',', ' ').split()
					options['start_date'] 	 = self.acc_start_date_box.text()
					options['end_date']		 = self.acc_end_date_box.text()
					#options['DOB']			 = self.acc_dob_box.text()
					options['modality']		 = self.acc_modality_box.text()
					options['exclude_terms'] = (self.acc_keyword_box.text()).replace(',', ' ').split()
					options['verbose'] 		 = True
					options['keep_phi'] 	 = False

			elif self.keyword_btn.isChecked():
				options['search_type'] = "keyword"
				options['review']      = True
				if self.maninput_btn.isChecked():
					query_terms 			 = (self.key_box.text()).replace(',', ' ').split()
					options['start_date'] 	 = self.key_start_date_box.text()
					options['end_date']		 = self.key_end_date_box.text()
					#options['DOB']			 = self.key_dob_box.text()
					options['modality']		 = self.key_modality_box.text()
					options['exclude_terms'] = (self.key_keyword_box.text()).replace(',', ' ').split()
					options['verbose'] 		 = True
					options['keep_phi'] 	 = False
			else:
				return None
			################Getting input from CSV File################
			if self.csv_btn.isChecked():

				query_terms				 = options['csv_file']
				options['start_date'] 	 = ''
				options['end_date']   	 = ''
				#options['DOB'] 		  	 = ''
				options['modality']   	 = ''
				options['exclude_terms'] = ''
				options['verbose']		 = True
				options['keep_phi'] 	 = False
			
			self.collect_studies(user, pw, query_terms)
			#self.pushButton.clicked.connect(QtWidgets.QFileDialog.getExistingDirectory(self.savedir))
def main():
	app = QtWidgets.QApplication(sys.argv)  # A new instance of QApplication
	form = VNAGUI()  # We set the form to be our ExampleApp (design)
	form.show()  # Show the form
	app.exec_()  # and execute the app

if __name__ == '__main__':  # if we're running file directly and not importing it
	main()  # run the main function