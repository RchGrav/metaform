import sys, subprocess, os, time, signal, shutil
import ladybug as lb
P='/tmp/lb_crash'; shutil.rmtree(P,ignore_errors=True)
child=f'''
import ladybug as lb, os, signal, sys
d=lb.Database("{P}"); c=lb.Connection(d)
c.execute("CREATE NODE TABLE El(addr STRING, PRIMARY KEY(addr))")
c.execute("CREATE (:El {{addr:'committed'}})")
c.execute("BEGIN TRANSACTION"); c.execute("CREATE (:El {{addr:'uncommitted'}})")
print('killing',flush=True); os.kill(os.getpid(),signal.SIGKILL)
'''
r=subprocess.run([sys.executable,'-c',child],capture_output=True,text=True); print('child rc',r.returncode,r.stdout.strip())
d=lb.Database(P); c=lb.Connection(d)
q=c.execute("MATCH (e:El) RETURN e.addr"); o=[]
while q.has_next(): o.append(q.get_next()[0])
print('after SIGKILL + reopen:',o)
# does a read-only process opened earlier see later commits?
ro=f'''
import ladybug as lb,time
d=lb.Database("{P}",read_only=True); c=lb.Connection(d)
f=lambda: c.execute("MATCH (e:El) RETURN count(e)").get_next()[0]
print('ro start',f(),flush=True); time.sleep(3); print('ro after writer commit',f(),flush=True)
'''
p=subprocess.Popen([sys.executable,'-c',ro],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
time.sleep(1.5); c.execute("CREATE (:El {addr:'later'})"); print(p.communicate(timeout=20)[0][-250:])
t=time.time()
for i in range(2000): c.execute(f"CREATE (:El {{addr:'n{i}'}})")
print('autocommit creates/sec',round(2000/(time.time()-t)))
