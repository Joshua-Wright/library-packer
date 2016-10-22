#!/usr/bin/env python3 
import sys
import os
import shutil
import subprocess

tmpfolder     = ".tmp-package/"
main_filename = "main.c"

def sanatize_name(name):
    for x in "!@#$%^&*(){}[]:;\"'<>,./?\\|-+=":
        name = name.replace(x, '_')
    return name

def copy_pack_file(path, out_filename):
    objcopy = subprocess.run(['objcopy', '-I', 'binary', '-B', 'i386:x86-64', '-O', 'elf64-x86-64', path, out_filename])

def lib_data_start(lib_name):  return "(&_binary_"           + sanatize_name(lib_name) + "_start[0])"
def lib_data_length(lib_name): return "((long int)&_binary_" + sanatize_name(lib_name) + "_size)"
def write_decl(outfile, libs, payload):
    outfile.write("// objcopy puts the size as the address of the symbol\n")
    for lib in libs:
        outfile.write('extern const char _binary_'     + sanatize_name(lib)     + '_start[];\n')
        outfile.write('extern const long int _binary_' + sanatize_name(lib)     + '_size;\n')
    outfile.write('extern const char _binary_'         + sanatize_name(payload) + '_start[];\n')
    outfile.write('extern const long int _binary_'     + sanatize_name(payload) + '_size;\n')

if __name__ == "__main__":

    if len(sys.argv) < 3:
        print("usage:", sys.argv[0], "<input> <output>")
        exit(1)

    # find libraries
    payload = sys.argv[1]
    target  = sys.argv[2]
    ldd_output = subprocess.run(["ldd", payload], stdout=subprocess.PIPE)
    libs = []
    for line in ldd_output.stdout.decode('utf-8').split('\n'):
        if " => " in line:
            lib = line.split(' ')[2]
            if lib != '': 
                libs.append(lib)

    # make libs folder
    if not os.path.exists(tmpfolder):
        os.mkdir(tmpfolder)
    # make master libs C file
    with open(tmpfolder+main_filename, "w") as out:
        # write starting info
        out.write("#include <stdlib.h>\n")
        out.write("#include <stdint.h>\n")
        out.write('#include <unistd.h>\n')
        out.write('#include <fcntl.h>\n')
        out.write('#include <sys/stat.h>\n')
        out.write('#include <wait.h>\n')
        out.write('#include <stdio.h>\n')
        out.write('#include <string.h>\n')
        out.write('#include <errno.h>\n')

        # expose extern variables
        write_decl(out, libs, payload)

        out.write('int main(int argc, char **argv) {')
        out.write('int fd;\n')
        out.write('char ld_lib_path[512] = {0};\n')
        out.write('char libpathbuf[256] = {0};\n')
        out.write('char baselibpath[256] = {0};\n')
        out.write('sprintf(baselibpath, "/dev/shm/%d/", getpid());\n')
        out.write('mkdir(baselibpath, 0700);\n')
        for lib in libs:
            out.write('sprintf(libpathbuf, "%s/%s", baselibpath, "'+os.path.basename(lib)+'");\n')
            out.write('fd = open(libpathbuf, O_RDWR | O_CREAT, 0700);\n')
            out.write('write(fd, '+lib_data_start(lib)+', '+lib_data_length(lib)+');\n')
            out.write('close(fd);\n')
            out.write('strcat(ld_lib_path, ":");\n')
            out.write('strcat(ld_lib_path, libpathbuf);\n')
        # set env
        out.write('setenv("LD_LIBRARY_PATH", ld_lib_path+1, 1);\n')
        # write payload
        out.write('sprintf(libpathbuf, "%s/%s", baselibpath, "'+os.path.basename(payload)+'");\n')
        out.write('fd = open(libpathbuf, O_RDWR | O_CREAT, 0700);\n')
        out.write('write(fd, '+lib_data_start(payload)+', '+lib_data_length(payload)+');\n')
        out.write('close(fd);')

        out.write('int pid = vfork();\n')
        out.write('if (!pid){\n')
        # intentionally don't overwrite argv[0]
        out.write('execv(libpathbuf, argv);\n')
        out.write('printf("error unpacking: %s", strerror(errno));\n')
        out.write('}\n')

        out.write('waitpid(pid, NULL, 0);\n')
        for lib in libs:
            out.write('sprintf(libpathbuf, "%s/%s", baselibpath, "'+os.path.basename(lib)+'");\n')
            out.write('unlink(libpathbuf);\n')
        out.write('sprintf(libpathbuf, "%s/%s", baselibpath, "'+os.path.basename(payload)+'");\n')
        out.write('unlink(libpathbuf);\n')
        out.write('rmdir(libpathbuf);\n')
        out.write('}\n')

        # payload
        copy_pack_file(payload, tmpfolder+'payload')
        # lib data
        for lib in libs:
            basename = os.path.basename(lib)
            sanatized_name = sanatize_name(basename)
            copy_pack_file(lib, tmpfolder+sanatized_name)

    gcc = ['cc', '-Wno-unused-result','-static', '-O3', '-o', target, tmpfolder+main_filename, tmpfolder+'payload'] + [tmpfolder+sanatize_name(os.path.basename(l)) for l in libs]
    subprocess.run(gcc)
    shutil.rmtree(tmpfolder)

