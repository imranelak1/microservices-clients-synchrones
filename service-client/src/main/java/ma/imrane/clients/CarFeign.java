package ma.imrane.clients;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.*;
@FeignClient(name="SERVICE-VOITURE")
public interface CarFeign {
    @GetMapping("/api/cars/byClient/{id}") Car find(@PathVariable("id") long id);
}
