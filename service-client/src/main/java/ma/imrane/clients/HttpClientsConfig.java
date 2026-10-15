package ma.imrane.clients;
import org.springframework.context.annotation.*;
import org.springframework.cloud.client.loadbalancer.LoadBalanced;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
@Configuration
public class HttpClientsConfig {
    @Bean @LoadBalanced RestTemplate restTemplate() {
        var factory=new SimpleClientHttpRequestFactory();factory.setConnectTimeout(3000);factory.setReadTimeout(5000);
        return new RestTemplate(factory);
    }
    @Bean @LoadBalanced WebClient.Builder webClientBuilder() {return WebClient.builder();}
}
