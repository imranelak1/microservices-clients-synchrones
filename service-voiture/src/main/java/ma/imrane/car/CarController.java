package ma.imrane.car;
import org.springframework.web.bind.annotation.*;
import org.springframework.beans.factory.annotation.Value;
/** Payload stable, délai configurable ; la DB ne fausse pas cette comparaison HTTP. */
@RestController
public class CarController {
    public record Car(long id,String marque,String modele,long clientId,String details) { }
    private final long delay;
    public CarController(@Value("${car.delay-ms:20}") long delay) {this.delay=delay;}
    @GetMapping("/api/cars/byClient/{clientId}")
    public Car byClient(@PathVariable long clientId) throws InterruptedException {
        if(delay>0) Thread.sleep(delay);
        return new Car(clientId*10,"Toyota","Yaris",clientId,"x".repeat(3000));
    }
}
