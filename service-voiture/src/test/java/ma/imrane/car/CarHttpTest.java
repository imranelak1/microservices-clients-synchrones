package ma.imrane.car;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT,properties={"spring.cloud.discovery.enabled=false","spring.cloud.consul.enabled=false","eureka.client.enabled=false","car.delay-ms=0"})
class CarHttpTest {
    @Autowired TestRestTemplate http;
    @Test void carResponseHasStablePayload() {var car=http.getForObject("/api/cars/byClient/7",CarController.Car.class);assertEquals(70,car.id());assertEquals(7,car.clientId());assertEquals(3000,car.details().length());}
    @Test void healthIsAvailable() {assertEquals(200,http.getForEntity("/actuator/health",String.class).getStatusCode().value());}
}
