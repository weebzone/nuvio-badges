import java.io.*;
import java.util.*;
import java.util.regex.*;

// Reads "name\tpattern" lines, then "--", then test lines; prints matched names per test.
// Uses java.util.regex, the same engine Nuvio uses on Android.
public class Check {
    public static void main(String[] a) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, "UTF-8"));
        LinkedHashMap<String, Pattern> rules = new LinkedHashMap<>();
        String line;
        while (!(line = in.readLine()).equals("--")) {
            String[] p = line.split("\t", 2);
            rules.put(p[0], Pattern.compile(p[1]));
        }
        while ((line = in.readLine()) != null) {
            String text = line.replace("\\n", "\n");
            List<String> hit = new ArrayList<>();
            rules.forEach((n, p) -> { if (p.matcher(text).find()) hit.add(n); });
            System.out.println(String.join("|", hit));
        }
    }
}
