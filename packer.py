#!/usr/bin/env python3 
import sys
import os
import shutil
import subprocess

tmpfolder     = ".tmp-package/"
main_filename = "main.cpp"

def sanatize_name(name):
    for x in "!@#$%^&*(){}[]:;\"'<>,./?\\|-+=":
        name = name.replace(x, '_')
    return name

def copy_pack_file(path, out_filename):
    objcopy = subprocess.run(['objcopy', '-I', 'binary', '-B', 'i386:x86-64', '-O', 'elf64-x86-64', path, out_filename])

def lib_data_start(lib_name):  return "(&_binary_"           + sanatize_name(lib_name) + "_start[0])"
def lib_data_length(lib_name): return "((long int)&_binary_" + sanatize_name(lib_name) + "_size)"
def write_decl(outfile, libs, payload):
    # objcopy puts the size as the address of the symbol
    for lib in libs:
        outfile.write('extern const char _binary_'     + sanatize_name(lib) + '_start[];\n')
        outfile.write('extern const long int _binary_' + sanatize_name(lib) + '_size;\n')
    outfile.write('extern const char _binary_'     + sanatize_name(payload) + '_start[];\n')
    outfile.write('extern const long int _binary_' + sanatize_name(payload) + '_size;\n')

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
        out.write("""
        #include <stdlib.h>
        #include <stdint.h>
        #include <unistd.h>
        #include <fcntl.h>
        #include <sys/stat.h>
        #include <wait.h>
        #include <stdio.h>
        #include <string.h>
        #include <errno.h>
        #include <iostream>
        #include <sstream>
        #include <string>

        extern char **environ;
        """)
        # expose extern variables
        write_decl(out, libs, payload)

        out.write("""
        int main(int argc, char **argv) {
            using namespace std;
            int fd = -1;
            stringstream ld_lib_path;
            //ld_lib_path << "LD_PRELOAD=";
            string tmppath = "/tmp/";
            string libpathbuf;
            if (getenv("TMPDIR")) {
                tmppath = getenv("TMPDIR");
            }
            string baselibpath = tmppath + "/llib_XXXXXX";
        """)

        for lib in libs:
            out.write("""
                libpathbuf = baselibpath;
                fd = mkstemp(&libpathbuf[0]);
                unlink(libpathbuf.c_str());
                if (write(fd, {start}, {length}) != {length}) {{return 1;}};
                ld_lib_path << "/dev/fd/" << fd << ":";
            """.format(
                basename=os.path.basename(lib), 
                start=lib_data_start(lib), 
                length=lib_data_length(lib))
            )
        # write payload (close and re-open to get read-only)
        out.write("""
            libpathbuf = tmppath + "payload_" + to_string(getpid());
            fd = open(libpathbuf.c_str(), O_RDWR | O_CREAT | O_EXCL, 0700);
            if (write(fd, {start}, {length}) != {length}) {{return 1;}};
            close(fd);
            fd = open(libpathbuf.c_str(), O_RDONLY);
            unlink(libpathbuf.c_str());
        """.format(
            start=lib_data_start(payload), 
            length=lib_data_length(payload))
        )

        out.write("""
            string envbuf = ld_lib_path.str();
            envbuf.pop_back();
            setenv("LD_PRELOAD", envbuf.c_str(), 1);
            fexecve(fd, argv, environ);
            return 1;
        }
        """)

        # payload
        copy_pack_file(payload, tmpfolder+'payload')
        # lib data
        for lib in libs:
            basename       = os.path.basename(lib)
            sanatized_name = sanatize_name(basename)
            copy_pack_file(lib, tmpfolder+sanatized_name)

    gcc = ['c++', '--std=c++11', '-static', '-Os', '-o', target, tmpfolder+main_filename, tmpfolder+'payload'] + [tmpfolder+sanatize_name(os.path.basename(l)) for l in libs]
    subprocess.run(gcc)
    shutil.rmtree(tmpfolder)

