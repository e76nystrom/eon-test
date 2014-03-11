from msaGlobal import SetModuleVersion
from collections import defaultdict
from gc import collect, get_objects
#import objgraph   # JGH requires python-objgraph module

SetModuleVersion("memLeak",("1.03","EON","03/11/2014"))

objdump = 5
fill_before = True
before = defaultdict(int)
fil = open("dbg.txt","w")
fil.close()

def memInit():
    global objdump, fill_before
    if fill_before:
        fill_before = False
        collect()
        objects = get_objects()
        for obj in objects:
            before[id(obj)] = 1
            objects = None

def memCheck():
    global objdump, fill_before
    collect()
    objects = get_objects()
    fil = open("dbg.txt","a")
    i = 0
    for obj in objects:
        if before[id(obj)] == 0:
            objtype = type(obj).__name__
            if  objtype != 'frame':
                if objtype == 'instancemethod':
                    fil.write("i - %3d %8x %s\n" % (i, id(obj), obj.__name__))
                    #if objdump > 0:
                    #    objdump -= 1
                    #    objgraph.show_backrefs(obj, filename="obj%d.png" % (objdump))
                elif objtype == 'instance':
                    if obj.__class__ != '__main__.Event':
                        fil.write("t - instance %s\n" % (obj.__class__))
                elif objtype == 'tuple':
                    fil.write("t - tuple %3d %s\n" % (len(obj), obj))
                elif objtype == 'dict':
                    fil.write("t - dict %3d\n" % (len(obj)))
                    if False:
                        for val in obj.keys():
                            fil.write("%s %s\n" % (val, obj[val]))
                            break
                else:
                    fil.write("t - %s %8x\n" % (objtype, id(obj)))
                i += 1
    fil.write("total %4d\n\n" % (i))
    fil.close()

