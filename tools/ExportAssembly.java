// Export only assembly and the function index required by recomp-kit.
// No generated pseudocode is used as source and no game function is replaced.
// @category GTASAWeb
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;

public class ExportAssembly extends GhidraScript {
    public void run() throws Exception {
        Path out = Path.of(getScriptArgs()[0], currentProgram.getName());
        Files.createDirectories(out.resolve("functions"));
        int total = 0;
        long instructionCount = 0;
        try (PrintWriter index = new PrintWriter(Files.newBufferedWriter(
                out.resolve("functions.tsv"), StandardCharsets.UTF_8))) {
            index.println("address\tname\tbytes\tstatus\tmessage");
            FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
            while (functions.hasNext()) {
                monitor.checkCancelled();
                Function f = functions.next();
                if (f.isExternal()) continue;
                String address = f.getEntryPoint().toString();
                long count = 0;
                try (PrintWriter asm = new PrintWriter(Files.newBufferedWriter(
                        out.resolve("functions/" + address + ".asm"), StandardCharsets.UTF_8))) {
                    InstructionIterator instructions = currentProgram.getListing().getInstructions(f.getBody(), true);
                    while (instructions.hasNext()) {
                        Instruction ins = instructions.next();
                        asm.printf("%s  %s%n", ins.getAddress(), ins.toString());
                        count++;
                    }
                }
                index.printf("%s\t%s\t%d\tassembly\t%n", address, f.getName(), f.getBody().getNumAddresses());
                total++;
                instructionCount += count;
                if (total % 500 == 0) {
                    index.flush();
                    println("Exported assembly for " + total + " functions");
                }
            }
        }
        Files.writeString(out.resolve("assembly-summary.json"),
            "{\"functions\":" + total + ",\"instructions\":" + instructionCount + "}");
        println("Assembly export complete: " + total + " functions, " + instructionCount + " instructions");
    }
}
