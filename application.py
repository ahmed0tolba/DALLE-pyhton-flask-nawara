# from _typeshed import Self
# pip install flask script
import sqlite3
import click
from flask.cli import with_appcontext
from flask import Flask,make_response,url_for,redirect, request, render_template,current_app, g, send_file
from viz_t_s_eliot import getSaveImagesRepresentingTask
application = Flask(__name__)
import sqlite3
import datetime
from threading import Thread
import gc
import os
import urllib
from transformers import CLIPProcessor, FlaxCLIPModel
import zipfile
import time
from io import BytesIO

# Don't forget 16 to 32 and 8 images
from dalle_mini.model import CustomFlaxBartForConditionalGeneration
from transformers import BartTokenizer
DALLE_REPO = 'flax-community/dalle-mini'
DALLE_COMMIT_ID = '4d34126d0df8bc4a692ae933e3b902a1fa8b6114'
# global tokenizer
# global model
# def do_at_startup():
print('Server is starting up! , Please wait while loading model')  
tokenizer = BartTokenizer.from_pretrained(DALLE_REPO, revision=DALLE_COMMIT_ID)
model = CustomFlaxBartForConditionalGeneration.from_pretrained(DALLE_REPO, revision=DALLE_COMMIT_ID)
clip = FlaxCLIPModel.from_pretrained("openai/clip-vit-base-patch32")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

print("Model loaded")
# ftfy # spacy

# global numberofrunningtasks
# numberofrunningtasks = 0
numberofrunningtasksmax = 1
databasename = 'static/_database.db'
searchestextstable = 'searchestextstable'
resultImagestable = 'resultImagestable'
# numofimages = 2
try:
  print(f'Checking if {databasename} exists or not...')
  conn = sqlite3.connect(databasename, uri=True)
  print(f'Database exists. Succesfully connected to {databasename}')
  conn.execute('CREATE TABLE IF NOT EXISTS ' + searchestextstable+ ' (id INTEGER PRIMARY KEY AUTOINCREMENT,searchsentense TEXT UNIQUE NOT NULL, numofimages INTEGER NOT NULL, states INTEGER NOT NULL,resultsevaluation Integer DEFAULT -1, insertdate timestamp NOT NULL, startdate timestamp, finishdate timestamp)')
  # resultsevaluation 0 -> not evaluate , 1 evaluated , 2 all results are bad
  # state 0 -> waiting , 1 -> processing , 2 -> done
  print(f'Succesfully Created Table {searchestextstable}')
  conn.execute('CREATE TABLE IF NOT EXISTS ' + resultImagestable + ' (id INTEGER PRIMARY KEY AUTOINCREMENT,searchsentense TEXT NOT NULL,imgname TEXT UNIQUE NOT NULL , states INTEGER NOT NULL, evaluation INTEGER DEFAULT 0)')
  print(f'Succesfully Created Table {resultImagestable}')
  
except sqlite3.OperationalError as err:
  print('Database does not exist')
  print(err)



def vizthread(searchtext,numofimages,tokenizer,model,clip,processor):
  
  # conn = sqlite3.connect(databasename, uri=True)
  connt = sqlite3.connect(databasename, uri=True)
  curt = connt.cursor()
  
  sql_update_query = """Update searchestextstable set states = 1,startdate = ? where searchsentense = ?"""
  data_tuple = (datetime.datetime.now(),searchtext)
  curt.execute(sql_update_query,data_tuple)
  connt.commit()
  for x in range(int(numofimages)):
    sqlite_insert_query = """Update resultImagestable set states = 1 where imgname = ?"""                          
    data_tuple = (searchtext+"_"+str(x),)
    curt.execute(sqlite_insert_query,data_tuple)
    connt.commit()
  connt.close()
  try:
    getSaveImagesRepresentingTask(searchtext,numofimages,tokenizer,model,clip,processor)
  except:
    sql_update_query = """Update searchestextstable set states = 0,startdate = ? where searchsentense = ?"""
    data_tuple = (datetime.datetime.now(),searchtext)
    connt = sqlite3.connect(databasename, uri=True)
    curt = connt.cursor()  
    curt.execute(sql_update_query,data_tuple)
    connt.commit()
    for x in range(int(numofimages)):
      sqlite_insert_query = """Update resultImagestable set states = 0 where imgname = ?"""                          
      data_tuple = (searchtext+"_"+str(x),)
      curt.execute(sqlite_insert_query,data_tuple)
      connt.commit()
    connt.close()
  
  connt = sqlite3.connect(databasename, uri=True)
  curt = connt.cursor()
  sql_update_query = """Update searchestextstable set states = 2,finishdate = ? where searchsentense = ?"""
  data_tuple = (datetime.datetime.now(),searchtext)
  curt.execute(sql_update_query,data_tuple)
  connt.commit()
  for x in range(int(numofimages)):
    sqlite_insert_query = """Update resultImagestable set states = 2 where imgname = ?"""                          
    data_tuple = (searchtext+"_"+str(x),)
    curt.execute(sqlite_insert_query,data_tuple)
    connt.commit()
  
  curt.execute('select * from '+ searchestextstable +' where states = ?', (1,))
  records = curt.fetchall()
  numberofrunningtasks = len(records)
  print("a job Finished, Number of running tasks running = " + str(numberofrunningtasks))
  
  curt.execute('select * from '+ searchestextstable +' where states = ?', (0,))
  recordsq = curt.fetchall()
  numberofqueuedtasks = len(recordsq)
  # checking if there is another task to do # checking for queued jobs
  while numberofrunningtasks < numberofrunningtasksmax and numberofqueuedtasks > 0:
    for row in recordsq:
      searchsentense = row[1]
      numofimages = row[2]
      sql_update_query = """Update searchestextstable set states = 1,startdate = ? where searchsentense = ?"""
      data_tuple = (datetime.datetime.now(),searchsentense)
      curt.execute(sql_update_query,data_tuple)
      connt.commit()
      for x in range(int(numofimages)):
        sqlite_insert_query = """Update resultImagestable set states = 1 where imgname = ?"""                          
        data_tuple = (searchsentense+"_"+str(x),)
        curt.execute(sqlite_insert_query,data_tuple)
        connt.commit()
      connt.close()
      print("'"+searchsentense+"'"+ " was in queu , and now is running")
      try:
        getSaveImagesRepresentingTask(searchsentense,numofimages,tokenizer,model,clip,processor)
      except:
        sql_update_query = """Update searchestextstable set states = 0,startdate = ? where searchsentense = ?"""
        data_tuple = (datetime.datetime.now(),searchsentense)
        connt = sqlite3.connect(databasename, uri=True)
        curt = connt.cursor()  
        curt.execute(sql_update_query,data_tuple)
        connt.commit()
        for x in range(int(numofimages)):
          sqlite_insert_query = """Update resultImagestable set states = 0 where imgname = ?"""                          
          data_tuple = (searchsentense+"_"+str(x),)
          curt.execute(sqlite_insert_query,data_tuple)
          connt.commit()
        connt.close()
      
      
      sql_update_query = """Update searchestextstable set states = 2,finishdate = ? where searchsentense = ?"""
      data_tuple = (datetime.datetime.now(),searchsentense)
      connt = sqlite3.connect(databasename, uri=True)
      curt = connt.cursor()  
      curt.execute(sql_update_query,data_tuple)
      connt.commit()
      for x in range(int(numofimages)):
        sqlite_insert_query = """Update resultImagestable set states = 2 where imgname = ?"""                          
        data_tuple = (searchsentense+"_"+str(x),)
        curt.execute(sqlite_insert_query,data_tuple)
        connt.commit()
      connt.close()
      break

    # updating while variable    
    connt = sqlite3.connect(databasename, uri=True)
    curt = connt.cursor()        
    curt.execute('select * from '+ searchestextstable +' where states = ?', (1,))
    records2 = curt.fetchall()
    numberofrunningtasks = len(records2)
    curt.execute('select * from '+ searchestextstable +' where states = ?', (0,))
    recordsq = curt.fetchall()
    numberofqueuedtasks = len(recordsq)
      
  connt.close()
  # gc.collect()
  
  # return
  
# check if there are uncomplete tasks for a long time to reset
connt = sqlite3.connect(databasename, uri=True)
curt = connt.cursor()
curt.execute('select * from '+ searchestextstable +' where states = ?', (1,))
records = curt.fetchall()
numberofrunningtasks = len(records)
for row in records:
  searchsentense = row[1]  
  startdate = datetime.datetime.fromisoformat(row[6])
  perioud = datetime.datetime.now() - startdate
  if (perioud.total_seconds()/3600 > 1):
    sql_update_query = """Update searchestextstable set states = 0 where searchsentense = ?"""
    data_tuple = (searchsentense,)
    curt.execute(sql_update_query,data_tuple)
    connt.commit()
    print("'"+searchsentense+"'"+ " have reset and requeued, started processing more than an hour ago")

# processing queued tasks if any and maxtasks is not reached
curt.execute('select * from '+ searchestextstable +' where states = ?', (1,))
records = curt.fetchall()
numberofrunningtasks = len(records)

curt.execute('select * from '+ searchestextstable +' where states = ?', (0,))
records = curt.fetchall()
numberofqueuedtasks = len(records)
if numberofrunningtasks < numberofrunningtasksmax:  
  for row in records:
    searchsentense = row[1]
    numofimages = row[2]
    sql_update_query = """Update searchestextstable set states = 1,startdate = ? where searchsentense = ?"""
    data_tuple = (datetime.datetime.now(),searchsentense)
    curt.execute(sql_update_query,data_tuple)
    connt.commit()
    connt.close()
    print("'"+searchsentense+"'"+ " was in queu , and now is running")
    t0 = Thread(target=vizthread,args=[searchsentense,numofimages,tokenizer,model,clip,processor])
    t0.start()
    connt = sqlite3.connect(databasename, uri=True)
    curt = connt.cursor()  
    curt.execute('select * from '+ searchestextstable +' where states = ?', (1,))
    records2 = curt.fetchall()
    numberofrunningtasks = len(records2)
    if numberofrunningtasks >= numberofrunningtasksmax:
      break

connt.close()  


@application.route('/')
def index():
  goodImage = -1 # no previous image is marked as good
  message = "Write the text in the text input area. Click Generate Images. Wait for images to show up. Please rate each image."
  hiddenmessage = -1
  
  
  try:
    # print(request.cookies.get('lastsearch'))
    # print(base64.b64decode(urllib.unquote(request.cookies.get('lastsearch'))))
    # print("hi " + request.cookies.get('lastsearch'))
    lastsearch = urllib.parse.unquote(format(request.cookies.get('lastsearch'))) #.replace("\n"," ").replace("  "," ").strip()
    # print("hi " + lastsearch)
    # print("hi " + (urllib.parse.unquote(format(request.cookies.get('lastsearch')))))
    res = make_response(render_template('index.html')) 
    res.set_cookie('lastsearch',lastsearch) 
  except:
    lastsearch=""
  # print(lastsearch)
  conn = sqlite3.connect(databasename, uri=True)
  cur = conn.cursor()
  if ( len(lastsearch)<2 ):
    return render_template('index.html', message="Invalid input",hiddenmessage=-1,goodImage=goodImage)# redirect(url_for('mylink')) 
  if lastsearch=="":
    message = "Write the text in the text input area. Click Generate Images. Wait for images to show up. Please rate each image."
    
  else:
    sqlite_insert_query = """select * from searchestextstable
                          where searchsentense = ?;"""
    data_tuple = (lastsearch,)
    # print(sqlite_insert_query)
    cur.execute(sqlite_insert_query,data_tuple)
    rows = cur.fetchall()
    conn.close()
    for row in rows:
      searchsentense = row[1]
      numofimages = row[2]
      status = row[3]
      resultsevaluation = row[4]
      print ("current Status = " + str(status))
      if status == 0:
        message = "Your previous text is still in queue, you can add a new text or wait.."
        hiddenmessage = 0    
      elif status == 1:
        message = "Your previous text is being processed, you can add a new text or wait.."
        hiddenmessage = 1    
      elif status == 2:
        print ("resultsevaluation = " + str(resultsevaluation))
        if resultsevaluation == -1:
          message = "Your previous text completed succesfully, Please Select the best fit for the text."
          hiddenmessage = 2
        else:
          message = "Your previous text completed succesfully and was evaluated, you can view it any time."
          hiddenmessage = 2
        ##


        if resultsevaluation >= 0:
          # sqlite_insert_query = """select * from resultImagestable
          #                   where searchsentense = ? AND evaluation = ?;"""        
          # data_tuple = (lastsearch,1)
          # # print(sqlite_insert_query)
          # cur.execute(sqlite_insert_query,data_tuple)
          # rows = cur.fetchall()
          # if len(rows)> 0:
          #   for row in rows:
              goodImage = resultsevaluation
              # print("goodImage = " + str(goodImage))
        elif resultsevaluation ==-2:
          goodImage = -2
          # print("goodImage = " + str(goodImage))

  return render_template('index.html',message=message,hiddenmessage=hiddenmessage,goodImage=goodImage)

@application.route('/',methods=['POST'])
def mylink():
  message = "Hello"
  goodImage = -1
  hiddenmessage = -1
  alreadystored = 0
  form_name = request.form['form-name']
  
  if form_name == 'formrequest':
    textsearsh = format(request.form['textsearsh']).replace("\n"," ").replace("  "," ").strip()
    res = make_response(render_template('index.html')) 
    res.set_cookie('lastsearch',textsearsh) 
    
    print ('You entered: ' , textsearsh)
    numofimages = format(request.form['numberofimages'])
    # print(format(request.form['textsearsh'])) 
    if ( len(textsearsh.strip())<2 ):
      return render_template('index.html', message="Invalid input",hiddenmessage=-1)# redirect(url_for('mylink'))  
    
    
    # if not in database , add to database 
    sqlite_insert_query = """select * from searchestextstable
                            where searchsentense = ?;"""
    data_tuple = (textsearsh,)
    # print(sqlite_insert_query)
    conn = sqlite3.connect(databasename, uri=True)
    cur = conn.cursor()
    cur.execute(sqlite_insert_query,data_tuple)
    rows = cur.fetchall()
    conn.close()
    searchedtextindatabase = len(rows)
    alreadyindatabase = False
    if searchedtextindatabase > 0:
      alreadyindatabase = True
      for row in rows:
        status = row[3]
        if status == 0:
          message = "'"+textsearsh+"'"+ " is still in queue, you can add a new text or wait.."
          hiddenmessage = 0    
        elif status == 1:
          message = "'"+textsearsh+"'"+" is being processed, you can add a new text or wait.."
          hiddenmessage = 1    
        elif status == 2:
          message = "'"+textsearsh+"'"+" completed succesfully, you can add a new text."
          hiddenmessage = 2
      
      # message = "'"+textsearsh+"'"+ " --> is already in database"
      hiddenmessage = 0
      print(message)
    else:
      hiddenmessage = 0
      sqlite_insert_query = """INSERT INTO searchestextstable
                          (searchsentense, numofimages , states, insertdate) 
                            VALUES 
                          (?,?,?,?);"""
      data_tuple = (textsearsh, numofimages, 0,datetime.datetime.now())
      conn = sqlite3.connect(databasename, uri=True)
      cur = conn.cursor()
      cur.execute(sqlite_insert_query,data_tuple)
      conn.commit()

      conn = sqlite3.connect(databasename, uri=True)
      cur = conn.cursor()        
      for x in range(int(numofimages)):
        sqlite_insert_query = """INSERT INTO resultImagestable
                            (searchsentense ,imgname , states) 
                              VALUES 
                            (?,?,?);"""
        data_tuple = (textsearsh,textsearsh+"_"+str(x), 0)
        cur.execute(sqlite_insert_query,data_tuple)
        conn.commit()
      
      conn.close()
      
      message = "'"+textsearsh+"'"+ " --> is queued for processing and will be processed soon, results will be updated automatically , you can close the page and come back later" 
      print(message)

    
    # if (not alreadyindatabase):
    #   
    #   
      
    conn = sqlite3.connect(databasename, uri=True)
    cur = conn.cursor()
        
    cur.execute('select * from '+ searchestextstable +' where states = ?', (1,))
    records = cur.fetchall()
    conn.close()
    numberofrunningtasks = len(records)
    print("numberofrunningtasks = ", numberofrunningtasks)
    if not alreadyindatabase:
      if numberofrunningtasks < numberofrunningtasksmax:
        numberofrunningtasks = numberofrunningtasks +1
        message = "'"+textsearsh+"'"+" job Started, Number of running tasks running = " + str(numberofrunningtasks) + " , results will be updated automatically , you can close the page and come back later"
        print(message )
              
        t = Thread(target=vizthread,args=[textsearsh,numofimages,tokenizer,model,clip,processor])
        t.start()
      else:
        message = "Server is busy - maximum processes are runing - ", "'",textsearsh,"'"," job will be qued , Number of running tasks running = " + str(numberofrunningtasks) + " , results will be updated automatically , you can close the page and come back later"
        print(message)

    sqlite_insert_query = """select * from searchestextstable
                            where searchsentense = ?;"""
    data_tuple = (textsearsh,)
    # print(sqlite_insert_query)
    conn = sqlite3.connect(databasename, uri=True)
    cur = conn.cursor()
        
    cur.execute(sqlite_insert_query,data_tuple)
    rows = cur.fetchall()
    conn.close()
    for row in rows:
      resultsevaluation = row[4]
      if resultsevaluation == -1: # no evaluation was entered , take the evaluation
        pass
      else: # evaluation was entered previously, refuse evaluation
        message = "Results were previously stored. Contact Admin for modifications"
        alreadystored = 1
        goodImage = resultsevaluation

  if form_name == 'formfeedback':
    x = request.form['selectedimageNum']
    nam = request.form['shownimagesName'] # nam is the images shown search text , the text in the box might have changed
    
    sqlite_insert_query = """select * from searchestextstable
                            where searchsentense = ?;"""
    data_tuple = (nam,)
    # print(sqlite_insert_query)
    conn = sqlite3.connect(databasename, uri=True)
    cur = conn.cursor()
    cur.execute(sqlite_insert_query,data_tuple)
    rows = cur.fetchall()
    conn.close()
    for row in rows:
      resultsevaluation = row[4]
      if resultsevaluation == -1: # no evaluation was entered , take the evaluation
        sql_update_query = """Update searchestextstable set resultsevaluation = ? where searchsentense = ?"""
        if (x=="-2"):
          statesnum = -2 
        else: 
          statesnum = int(x)
        print(x,nam)
        print("statesnum = " + str (statesnum))
        data_tuple = (statesnum,nam)
        conn = sqlite3.connect(databasename, uri=True)
        cur = conn.cursor()
        cur.execute(sql_update_query,data_tuple)
        conn.commit()
        
        if int(x) >= 0:
          goodImage = x
          sql_update_query = """Update resultImagestable set evaluation = ? where imgname = ?"""
          data_tuple = (1,nam+"_"+str(x))
          cur.execute(sql_update_query,data_tuple)
          conn.commit()
        
        message = "Thanks You, Your feedback is stored successfully, you may view it any time by entering the same text. You can close the page or start a new search."
        print (message)
        alreadystored = 1



      else: # evaluation was entered previously, refuse evaluation
        

        goodImage = x 
        
        message = "Results were previously stored. Contact Admin for modifications"
        alreadystored = 1

    
  conn.close()
  # print (message,2)
  result=1
  # result=textsearsh+"_1.png"
  return render_template('index.html', message=message,hiddenmessage=hiddenmessage,goodImage=goodImage,alreadystored=alreadystored)# redirect(url_for('mylink'))#render_template('index.html')#, result=textsearsh+"_1.png")#

@application.route('/results/')
def allresults():
  conn = sqlite3.connect(databasename, uri=True)
  cur = conn.cursor()
  cur.execute("SELECT * from searchestextstable")
  data = cur.fetchall()
  return render_template('results.html',data=data)



@application.route('/download/')
def downloadFile ():
    timestr = time.strftime("%Y%m%d-%H%M%S")
    fileName = "my_data_dump_{}.zip".format(timestr)
    memory_file = BytesIO()
    file_path = 'static/'

    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
      for root,dirs, files in os.walk(file_path):
        for file in files:
          zipf.write(os.path.join(root, file))
    memory_file.seek(0)
    return send_file(memory_file,
                     attachment_filename=fileName,
                     as_attachment=True)
    # path = 'static/_database.db'
    # return send_file(path, as_attachment=True)


# DATABASE = '/static/_database.db'

# def get_db():
#     db = getattr(g, '_database', None)
#     if db is None:
#         db = g._database = sqlite3.connect(DATABASE)
#     return db

# @application.teardown_appcontext
# def close_connection(exception):
#     db = getattr(g, '_database', None)
#     if db is not None:
#         db.close()

# class server(Flask):
#   def run(self, host=None, port=None, debug=None, load_dotenv=True, **options):
    # if not self.debug or os.getenv('WERKZEUG_RUN_MAIN') == 'true':
      
    # super(MyFlaskApp, self).run(host=host, port=port, debug=debug, load_dotenv=load_dotenv, **options)

if __name__ == '__main__':
  application.run(debug=True,host="0.0.0.0",use_reloader=False)
    



# kwargs = {'host': '127.0.0.1', 'port': 5100, 'threaded': True, 'use_reloader': False, 'debug': True}
