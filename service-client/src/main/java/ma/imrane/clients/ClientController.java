package ma.imrane.clients;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.http.*;
import java.time.Duration;
import java.util.Map;
/** Les trois endpoints attendent le même payload, dans les mêmes conditions. */
@RestController
public class ClientController {
    private final RestTemplate rest;
    private final CarFeign feign;
    private final WebClient web;
    public ClientController(RestTemplate rest,CarFeign feign,WebClient.Builder builder) {this.rest=rest;this.feign=feign;this.web=builder.build();}
    @GetMapping("/api/clients/{id}/car/rest") public Car rest(@PathVariable long id) {return rest.getForObject("http://SERVICE-VOITURE/api/cars/byClient/"+id,Car.class);}
    @GetMapping("/api/clients/{id}/car/feign") public Car feign(@PathVariable long id) {return feign.find(id);}
    @GetMapping("/api/clients/{id}/car/webclient") public Car webclient(@PathVariable long id) {return web.get().uri("http://SERVICE-VOITURE/api/cars/byClient/"+id).retrieve().bodyToMono(Car.class).timeout(Duration.ofSeconds(5)).block();}
    @ExceptionHandler(Exception.class) public ResponseEntity<Map<String,String>> unavailable(Exception error) {return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(Map.of("error","Service voiture indisponible"));}
}
