"""Verify undocumented group-2 /6 against /4 on actual Windows x86 hardware."""
from pathlib import Path
import json
import os
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    vswhere=Path(os.environ.get("ProgramFiles(x86)","C:/Program Files (x86)"))/"Microsoft Visual Studio/Installer/vswhere.exe"
    install=Path(subprocess.check_output([str(vswhere),"-latest","-products","*","-property","installationPath"],text=True).strip())
    vcvars=install/"VC/Auxiliary/Build/vcvars32.bat"
    if not vcvars.is_file() or '"' in str(vcvars):
        raise RuntimeError("32-bit Visual C++ tools unavailable")
    captured=subprocess.run(f'cmd.exe /d /c call "{vcvars}" >nul && set',capture_output=True,text=True,check=True)
    env={key.upper():value for key,value in os.environ.items()}
    for line in captured.stdout.splitlines():
        if "=" in line and not line.startswith("="):
            key,value=line.split("=",1)
            env[key.upper()]=value
    # Unique native fixture output; never overwrites a game build.
    output=ROOT/"build/sal-native-reference"
    output.mkdir(exist_ok=True)
    exe=output/"reference.exe"
    compiler=shutil.which("cl.exe",path=env["PATH"])
    if not compiler:
        raise RuntimeError("x86 compiler unavailable")
    subprocess.run([compiler,"/nologo","/W4","/Od","/TC",str(ROOT/"tools/sal_native_reference.c"),"/Fo"+str(output/"reference.obj"),"/Fe"+str(exe),"/link","/MACHINE:X86"],env=env,cwd=output,check=True)
    run=subprocess.run([str(exe)],capture_output=True,text=True,check=True,timeout=30)
    result=json.loads(run.stdout)
    rows=result["results"]
    assert len(rows)==336
    for row in rows:
        count=row["count"] & 31
        expected=(row["seed"] << count) & 0xffffffff
        assert row["sal_value"]==row["shl_value"]==expected,row
        # AF is undefined for nonzero shifts; OF is defined only for count1.
        # Count0 leaves all arithmetic flags unchanged, including AF and OF.
        mask=0x8d5 if count==0 else (0x8c5 if count==1 else 0xc5)
        assert (row["sal_flags"] ^ row["shl_flags"]) & mask==0,row
        assert (row["sal_flags"] ^ row["initial_flags"]) & 0x600==0,row # DF/IF unchanged
        if count==0:
            assert (row["sal_flags"] ^ row["initial_flags"]) & mask==0,row
        else:
            carry=(row["seed"] >> (32-count)) & 1
            parity=int((expected & 255).bit_count()%2==0)
            defined=carry | (parity << 2) | (int(expected==0) << 6) | ((expected >> 31) << 7)
            if count==1:
                defined |= (((expected >> 31) ^ carry) << 11)
            assert (row["sal_flags"] ^ defined) & mask==0,row
    report={"reference":"Actual Windows x86 execution of D3 F5 and C1 F5 imm8 versus group-2 /4 SHL", "cpuid_leaf0":result["cpuid_leaf0"],
            "case_pairs":len(rows),"native_instruction_executions":len(rows)*2,"results_equal_on_defined_flags":True,
            "undefined_flags":"AF for nonzero counts; OF for counts greater than one. Raw observations retained, not treated as portable guarantees.",
            "scope":"Observed group-2 /6 behavior on this CPU; not a guarantee for every x86 implementation or full game execution.","results":rows}
    (ROOT/"build/sal-native-reference.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({key:value for key,value in report.items() if key!="results"},indent=2))


if __name__=="__main__":
    main()
