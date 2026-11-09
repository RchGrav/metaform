import sys, subprocess, threading, time, os, shutil
import ladybug as lb
print('ladybug', getattr(lb,'__version__','?'), 'py', sys.version.split()[0])
P='/tmp/lb_spike'; shutil.rmtree(P,ignore_errors=True)
if os.path.exists(P): os.remove(P)
def step(n,f):
    try: print('OK  ',n,'=>',f())
    except Exception as e: print('FAIL',n,'=>',type(e).__name__,str(e)[:160])
db=lb.Database(P); c=lb.Connection(db)
c.execute("CREATE NODE TABLE El(addr STRING, PRIMARY KEY(addr))")
c.execute("CREATE REL TABLE PROV(FROM El TO El, op STRING, ef STRING, ifd STRING)")
c.execute("CREATE (:El {addr:'code.a'}),(:El {addr:'code.b'})")
count=lambda con: con.execute("MATCH (e:El) RETURN count(e)").get_next()[0]
def rollback():
    c.execute("BEGIN TRANSACTION"); c.execute("CREATE (:El {addr:'code.x'})"); c.execute("ROLLBACK"); return count(c)
step('rollback leaves 2',rollback)
def rel():
    c.execute("MATCH (a:El {addr:'code.a'}),(b:El {addr:'code.b'}) CREATE (a)-[:PROV {op:'o',ef:'e',ifd:'receive'}]->(b)")
    return c.execute("MATCH (a)-[r:PROV]->(b) RETURN a.addr,r.op,b.addr").get_next()
step('relationship properties',rel)
def snapshot():
    w=lb.Connection(db); r=lb.Connection(db)
    w.execute("BEGIN TRANSACTION"); w.execute("CREATE (:El {addr:'code.y'})")
    during=count(r); w.execute("COMMIT"); return ('reader during open write',during,'after',count(r))
step('reader isolation',snapshot)
def two_writers():
    a=lb.Connection(db); b=lb.Connection(db)
    a.execute("BEGIN TRANSACTION"); a.execute("CREATE (:El {addr:'code.w1'})")
    t=time.time()
    try:
        b.execute("BEGIN TRANSACTION"); b.execute("CREATE (:El {addr:'code.w2'})"); b.execute("COMMIT"); res='second writer succeeded'
    except Exception as e: res='second writer refused: '+str(e)[:110]
    a.execute("COMMIT"); return res, round(time.time()-t,3)
step('two concurrent write txns',two_writers)
code=f"import ladybug as lb\nd=lb.Database('{P}')\nc=lb.Connection(d)\nprint(c.execute('MATCH (e:El) RETURN count(e)').get_next())"
r=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=30)
print('second PROCESS opening same db RW while first open: rc',r.returncode,(r.stdout+r.stderr).strip()[-170:])
code2=f"import ladybug as lb\nd=lb.Database('{P}',read_only=True)\nc=lb.Connection(d)\nprint(c.execute('MATCH (e:El) RETURN count(e)').get_next())"
r=subprocess.run([sys.executable,'-c',code2],capture_output=True,text=True,timeout=30)
print('second PROCESS opening read_only while first RW open: rc',r.returncode,(r.stdout+r.stderr).strip()[-170:])
del c,db
import gc; gc.collect()
db=lb.Database(P); c=lb.Connection(db); print('restart count',count(c))
# crash durability: child commits then SIGKILL
