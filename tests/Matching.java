import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;
import java.util.regex.Pattern;

public class Matching {
    public static void main(String[] args) throws Exception {
        int count = 0;
        for (String line : Files.readAllLines(Path.of(args[0]))) {
            String[] cells = line.split("\t", -1);
            String pattern = new String(Base64.getDecoder().decode(cells[0]), StandardCharsets.UTF_8);
            String value = new String(Base64.getDecoder().decode(cells[1]), StandardCharsets.UTF_8);
            boolean actual = !Pattern.compile("[\\n\\r\\u0085\\u2028\\u2029]").matcher(value).find()
                    && Pattern.compile(pattern).matcher(value).matches();
            if (actual != Boolean.parseBoolean(cells[2])) throw new AssertionError(pattern + ": " + value);
            count++;
        }
        System.out.println("Java: " + count + " regex vectors passed");
    }
}
