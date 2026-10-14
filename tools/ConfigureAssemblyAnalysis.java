// Stack-variable/type recovery is unnecessary for instruction translation.
// Keep disassembly, function discovery and switch/jump-table analysis enabled.
// @category GTASAWeb
import ghidra.app.script.GhidraScript;
import ghidra.framework.options.Options;
import ghidra.program.model.listing.Program;

public class ConfigureAssemblyAnalysis extends GhidraScript {
    public void run() throws Exception {
        Options options = currentProgram.getOptions(Program.ANALYSIS_PROPERTIES);
        for (String name : new String[] {"Stack", "Decompiler Parameter ID"}) {
            if (options.contains(name)) {
                options.setBoolean(name, false);
                println("Disabled optional type analysis: " + name);
            }
        }
    }
}
